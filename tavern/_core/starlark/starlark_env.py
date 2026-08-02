"""Starlark environment setup for Tavern pipelines."""

import copy
import dataclasses
import logging
from typing import Any, TypedDict

import starlark

from tavern._core import exceptions
from tavern._core.exceptions import TavernException
from tavern._core.pytest.config import TestConfig
from tavern._core.run import _TestRunner
from tavern._core.strict_util import StrictLevel
from tavern._core.tincture import get_stage_tinctures

from .builtins import get_helpers_source, register_library_builtins, wrap_callable
from .response_struct import create_response_struct
from .stage_registry import StageRegistry
from .types import from_starlark, to_starlark

logger: logging.Logger = logging.getLogger(__name__)


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
            test_path: Path to the test file being run (used for error reporting in starlark parsing)
            stages: Optional list of stage dictionaries to register
        """
        self.test_path = test_path
        self.globals = starlark.Globals.standard().extended_by(
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
        module = starlark.Module()

        # Add built-in functions to module
        self._setup_builtins(module)

        # Parse the script
        dialect = starlark.Dialect.extended()
        dialect.enable_keyword_only_arguments = True

        try:
            ast = starlark.parse(self.test_path, script, dialect=dialect)
        except starlark.StarlarkError as e:
            logger.error("Failed to parse starlark script: %s", e)
            raise ValueError("Failed to parse starlark script") from e

        def load(filename: str) -> starlark.FrozenModule:
            """Implements the 'load' function in starlark. Currently only supports loading tavern helpers."""
            if filename == "@tavern_helpers.star":
                ast = starlark.parse(filename, get_helpers_source(), dialect=dialect)
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
            python_error = self._python_error
            if python_error is not None:
                exc = exceptions.StarlarkError("Error evaluating starlark script")
                exc.stage = python_error.stage  # type:ignore
                raise python_error from exc
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

        stage = copy.deepcopy(stage)  # Make a deep copy to avoid mutating nested dicts
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
        return create_response_struct(
            stage_response.response,
            success=stage_response.success,
            request_vars=stage_response.request_vars,
            stage_name=stage_response.stage_name,
        )

    def _setup_builtins(self, module: "starlark.Module") -> None:
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

        2. Add a wrapper function into builtins.register_library_builtins and add it
           with module.add_callable. dunder names are used to 'hide' the original
           function from the user.

            @wrap_callable
            def re_match(pattern, s):
                return re.match(pattern, s)

            @wrap_callable
            def re_sub(pattern, repl, s):
                return re.sub(pattern, repl, s)

            module.add_callable("__re_match", re_match)
            module.add_callable("__re_sub", re_sub)

           Anything registered there is also available in the per-stage expressions.

        3. Use from starlark by loading as before:

            load("@tavern_helpers.star", "re")

            resp = run_stage("my_stage")

            if not re.match("(one_thing|another_thing)", resp.json["key"]):
                fail("No match found")
        """
        for stage_id, stage in self._stage_registry.get_all_stages().items():
            module[stage_id] = to_starlark(stage)

        register_library_builtins(module)

        @wrap_callable
        def run_stage_binding(
            stage_id: str, continue_on_fail: bool, extra_vars: dict | None
        ) -> Any:
            stage = self._stage_registry.get_stage(stage_id)
            if stage is None:
                raise exceptions.StarlarkError(
                    f"Stage with id '{stage_id}' not found (had {list(self._stage_registry.get_all_stages().keys())}"
                )

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
