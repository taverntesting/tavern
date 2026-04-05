"""Starlark environment setup for Tavern pipelines."""

import dataclasses
import functools
import logging
import re
import time
from typing import Any, TypedDict

import requests
import starlark
from starlark import Dialect, Globals, Module

from tavern._core import exceptions
from tavern._core.exceptions import TavernException
from tavern._core.pytest.config import TestConfig
from tavern._core.run import _TestRunner
from tavern._core.strict_util import StrictLevel
from tavern._core.tincture import get_stage_tinctures

from .stage_registry import StageRegistry
from .types import from_starlark, to_starlark

logger: logging.Logger = logging.getLogger(__name__)


def _wrap_callable(fn):
    """Decorator that converts all arguments from starlark→Python before
    calling *fn*, and converts the return value from Python→starlark."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        converted_args = [from_starlark(a) for a in args]
        converted_kwargs = {k: from_starlark(v) for k, v in kwargs.items()}
        result = fn(*converted_args, **converted_kwargs)
        return to_starlark(result)

    return wrapper


class PipelineContext(TypedDict):
    """Context object passed between stages in starlark pipelines.

    This object carries the test configuration and sessions from one stage
    to the next, allowing users to explicitly manage the pipeline state.

    Attributes:
        test_config: The TestConfig with current variables
        sessions: Dictionary of session contexts
    """

    test_config: TestConfig
    sessions: dict[str, Any]


@dataclasses.dataclass
class StageResponse:
    """Response from running a stage.

    Attributes:
        success: True if all verifications passed
        response: The response body/headers/cookies/status_code
        request_vars: Any variables captured during the request
        stage_name: Name of the stage that was run
    """

    success: bool
    response: Any | None
    request_vars: dict[str, Any]
    stage_name: str

    def to_starlark(self) -> dict:
        return {
            "success": self.success,
            "response": to_starlark(self.response),
            "request_vars": to_starlark(self.request_vars),
            "stage_name": self.stage_name,
        }

    @classmethod
    def from_starlark(cls, obj: dict) -> "StageResponse":
        return cls(
            success=obj["success"],
            response=from_starlark(obj["response"]),
            request_vars=from_starlark(obj["request_vars"]),
            stage_name=obj["stage_name"],
        )


# language=starlark
_STARLARK_BUILTINS = """
def run_stage(name, *, continue_on_fail=False, extra_vars=None):
    resp = __run_stage(name, continue_on_fail, extra_vars)

    # Convert the dict to a starlark object
    return struct(
        # status_code=resp["status_code"],
        # Any other fields that should be exposed to starlark, which would be useful for testing. Possibly:
        # - response body loaded as json (could be a dict, or list, or string)
        # - variables (some may be opaque and unusable!)
        **resp
    )


def _re_match(pattern, s):
    m = __re_match(pattern, s)
    if m == None:
        return None
    return struct(group0=m["group0"], groups=m["groups"], start=m["start"], end=m["end"])


def _re_search(pattern, s):
    m = __re_search(pattern, s)
    if m == None:
        return None
    return struct(group0=m["group0"], groups=m["groups"], start=m["start"], end=m["end"])


def _re_sub(pattern, repl, s):
    return __re_sub(pattern, repl, s)


re = struct(match=_re_match, search=_re_search, sub=_re_sub)


def _time_sleep(seconds):
    __time_sleep(seconds)


time = struct(sleep=_time_sleep)
"""


class StarlarkPipelineRunner:
    """Runner for executing starlark pipeline scripts.

    This class handles loading and executing starlark scripts that can
    control the flow of test execution.
    """

    def __init__(
        self,
        test_path: str,
        stages: list[dict],
        test_config: TestConfig,
        sessions: dict[str, Any],
    ):
        """Initialize the pipeline runner.

        Args:
            test_config: The test configuration with variables
            sessions: session contexts to use for the pipeline
            test_path: Path to the .tavern.star file being run
            stages: Optional list of stage dictionaries to register
        """
        self.test_path = test_path
        self.globals = Globals.standard().extended_by(
            [
                starlark.LibraryExtension.StructType,
            ]
        )
        self._stage_registry = StageRegistry(stages) if stages else StageRegistry([])
        self._test_config: TestConfig = test_config
        self._sessions: dict[str, Any] = sessions
        self._python_error: BaseException | None = None
        self.stage_run = False

    def load_and_run(self, script: str) -> Any:
        """Load and run a starlark pipeline script.

        Args:
            script: The starlark script content

        Returns:
            The return value of the script, if any
        """
        # Create the starlark module
        module = Module()

        # Add built-in functions to module
        self._setup_builtins(module)

        # Parse the script
        dialect = Dialect.extended()
        dialect.enable_keyword_only_arguments = True

        try:
            ast = starlark.parse(self.test_path, script, dialect=dialect)
        except starlark.StarlarkError as e:
            logger.error("Failed to parse starlark script: %s", e)
            raise ValueError("Failed to parse starlark script") from e

        def load(filename: str) -> starlark.FrozenModule:
            """Implements the 'load' function in starlark. Currently only supports loading tavern helpers."""
            if filename == "@tavern_helpers.star":
                ast = starlark.parse(filename, _STARLARK_BUILTINS, dialect=dialect)
                mod = starlark.Module()
                self._setup_builtins(mod)
                starlark.eval(mod, ast, self.globals)
                return mod.freeze()
            raise FileNotFoundError(filename)

        # Evaluate the script
        try:
            starlark.eval(module, ast, self.globals, starlark.FileLoader(load))  # type: ignore[arg-type]
        except starlark.StarlarkError as e:
            logger.error("Error evaluating starlark script: %s", e)
            if self._python_error is not None:
                exc = exceptions.StarlarkError("Error evaluating starlark script")
                exc.stage = self._python_error.stage  # type:ignore
                raise self._python_error from exc
            else:
                exc = exceptions.StarlarkError("Error evaluating starlark script")  # type:ignore
                raise exc from e

        return None

    def _run_stage(
        self,
        stage: dict[str, Any],
        continue_on_fail: bool,
        extra_vars: dict | None = None,
    ) -> StageResponse:
        """Run a single stage and return the response.

        Args:
            stage: The stage specification dictionary
            continue_on_fail: if True, swallow TavernExceptions and return a
                              failed StageResponse instead of re-raising
            extra_vars: Additional variables to merge into test config for this stage

        Returns:
            StageResponse with the result of running the stage
        """

        self.stage_run = True

        stage = dict(stage)  # Make a copy to avoid mutating the original
        stage_name = stage.get("name", "unnamed-stage")

        default_strictness = StrictLevel.all_on()
        test_spec = {"test_name": "starlark-pipeline", "stages": [stage]}

        if extra_vars:
            test_config = self._test_config.with_new_variables()
            test_config.variables.update(extra_vars)
        else:
            test_config = self._test_config

        runner = _TestRunner(
            default_global_strictness=default_strictness,
            sessions=self._sessions,
            test_block_config=test_config,
            test_spec=test_spec,
        )

        try:
            tinctures = get_stage_tinctures(stage, test_spec)
            stage_config = test_config.with_strictness(default_strictness)
            response = runner.wrapped_run_stage(stage, stage_config, tinctures)

            return StageResponse(
                success=True,
                response=response,
                request_vars=test_config.variables,
                stage_name=stage_name,
            )

        except TavernException as e:
            logger.error("Stage '%s' failed: %s", stage_name, str(e), exc_info=True)
            if not continue_on_fail:
                self._python_error = e
                self._python_error.stage = stage
                raise
            return StageResponse(
                success=False,
                response=None,
                request_vars=test_config.variables,
                stage_name=stage_name,
            )

    def _create_response_struct(self, stage_response: StageResponse) -> dict[str, Any]:
        """Convert StageResponse to dict that starlark converts to struct."""
        base_dict: dict[str, Any] = {
            # Add "failed" so people don't have to do "if not resp.success" when people will almost certainly
            # want to do "if resp.failed" most of the time
            "failed": not stage_response.success,
            "success": stage_response.success,
            "request_vars": stage_response.request_vars,
            "stage_name": stage_response.stage_name,
        }
        if stage_response.response is None:
            return base_dict
        elif isinstance(stage_response.response, requests.Response):
            rest_response = stage_response.response
            content_type = rest_response.headers.get("Content-Type", "")

            base_dict.update(
                {
                    "status_code": rest_response.status_code,
                    "body": rest_response.json()
                    if "application/json" in content_type
                    else rest_response.content,
                    "headers": rest_response.headers,
                    "cookies": rest_response.cookies,
                }
            )
            return base_dict

        raise NotImplementedError(
            f"gRPC, MQTT, etc. are not supported yet. Got {type(stage_response.response)}"
        )

    def _setup_builtins(self, module: Module) -> None:
        """Set up built-in functions available in starlark scripts.

        Only a basic subset of types can be passed into starlark (anything that can be dumped to json).
        To create a simple wrapper script, define the function in the _STARLARK_BUILTINS string.

            def add(a, b):
                return a + b

        This can then be used easily from a 'control_flow' script:

            load("@tavern_helpers.star", "add")

            result = add(1, 2)
            log(result)  # logs '3'

        To create a more advanced wrapper, such as a 'library' module:

        1. create the basic wrapper functions and a global 'struct' in the _STARLARK_BUILTINS string.

            def _re_match(pattern, s):
                return __re_match(pattern, s)

            def _re_sub(pattern, repl, s):
                return __re_sub(pattern, repl, s)

            re = struct(match=_re_match, sub=_re_sub)

        2. Add a wrapper function into this function and add it with module.add_callable.
           dunder names are used to 'hide' the original function from the user.

            @_wrap_callable
            def re_match(pattern, s):
                return re.match(pattern, s)

            @_wrap_callable
            def re_sub(pattern, repl, s):
                return re.sub(pattern, repl, s)

            module.add_callable("__re_match", re_match)
            module.add_callable("__re_sub", re_sub)

        3. Use from starlark by loading as before:

            load("@tavern_helpers.star", "re")

            resp = run_stage("my_stage")

            if not re.match("(one_thing|another_thing)", resp.json["key"]):
                fail("No match found")
        """
        for stage_id, stage in self._stage_registry.get_all_stages().items():
            module[stage_id] = stage

        @_wrap_callable
        def run_stage_binding(
            stage_id: str, continue_on_fail: bool, extra_vars: dict | None
        ) -> Any:
            stage = self._stage_registry.get_stage(stage_id)
            if stage is None:
                raise exceptions.StarlarkError(
                    f"Stage with id '{stage_id}' not found (had {list(self._stage_registry.get_all_stages().keys())})"
                )

            if self._test_config is None:
                raise exceptions.StarlarkError("Test config not initialized")

            stage_response = self._run_stage(stage, continue_on_fail, extra_vars)
            try:
                return self._create_response_struct(stage_response)
            except Exception as e:
                logger.exception("Failed to convert stage response to struct")
                self._python_error = e
                self._python_error.stage = stage  # type:ignore
                raise exceptions.StarlarkError(
                    "Failed to convert stage response to struct"
                ) from e

        module.add_callable("__run_stage", run_stage_binding)

        @_wrap_callable
        def log(s: str) -> None:
            """log a string to stdout."""
            logger.info(s)

        module.add_callable("log", log)

        @_wrap_callable
        def re_match(pattern: str, string: str | bytes) -> dict | None:
            if isinstance(string, bytes):
                string = string.decode("utf-8")
            result = re.match(pattern, string)
            if result is None:
                return None
            return {
                "group0": result.group(0),
                "groups": list(result.groups()),
                "start": result.start(),
                "end": result.end(),
            }

        module.add_callable("__re_match", re_match)

        @_wrap_callable
        def re_search(pattern: str, string: str | bytes) -> dict | None:
            if isinstance(string, bytes):
                string = string.decode("utf-8")
            result = re.search(pattern, string)
            if result is None:
                return None
            return {
                "group0": result.group(0),
                "groups": list(result.groups()),
                "start": result.start(),
                "end": result.end(),
            }

        module.add_callable("__re_search", re_search)

        @_wrap_callable
        def re_sub(pattern: str, repl: str, string: str | bytes) -> str:
            if isinstance(string, bytes):
                string = string.decode("utf-8")
            return re.sub(pattern, repl, string)

        module.add_callable("__re_sub", re_sub)

        @_wrap_callable
        def time_sleep(seconds: float) -> None:
            time.sleep(seconds)

        module.add_callable("__time_sleep", time_sleep)
