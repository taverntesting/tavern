"""Starlark environment setup for Tavern pipelines."""

import dataclasses
import functools
import logging
import os
import pathlib
import tempfile
from typing import Any, TypedDict

import requests
import starlark
from starlark import Dialect, Globals, Module

from tavern._core import exceptions
from tavern._core.exceptions import TavernException
from tavern._core.loader import get_include_dirs, load_single_document_yaml
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


_STARLARK_BUILTINS = """
def run_stage(name, *, continue_on_fail=False):
    resp = __run_stage(name, continue_on_fail)

    # Convert the dict to a starlark object
    return struct(
        # status_code=resp["status_code"],
        # Any other fields that should be exposed to starlark, which would be useful for testing. Possibly:
        # - response body loaded as json (could be a dict, or list, or string)
        # - variables (some may be opaque and unusable!)
        **resp
    )
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

    def load_and_run(self, script: str, test_spec: dict[str, Any]) -> Any:
        """Load and run a starlark pipeline script.

        Args:
            script: The starlark script content
            test_spec: The test specification dictionary

        Returns:
            The return value of the script, if any
        """
        stages = test_spec.get("stages", [])
        self._stage_registry = StageRegistry(stages)

        # Create the starlark module
        module = Module()

        # Add built-in functions to module
        self._setup_builtins(module)

        # Parse the script
        dialect = Dialect.extended()

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                total = _STARLARK_BUILTINS + script
                with tempfile.NamedTemporaryFile(
                    delete=False, dir=tmpdir, suffix=".star"
                ) as f:
                    f.write(total.encode("utf-8"))
                    f.close()
                    logger.debug("Starlark script written to temporary file %s", f.name)
                ast = starlark.parse(f.name, total, dialect=dialect)
        except starlark.StarlarkError as e:
            logger.error("Failed to parse starlark script: %s", e)
            raise ValueError("Failed to parse starlark script") from e

        # Evaluate the script
        try:
            starlark.eval(module, ast, self.globals)  # type: ignore[arg-type]
            # result = module.freeze().call("run_pipeline")
        except starlark.StarlarkError as e:
            logger.error("Failed to evaluate starlark script: %s", e)
            raise RuntimeError("Failed to evaluate starlark script") from e

        return None

    def _run_stage(
        self,
        stage: dict[str, Any],
        continue_on_fail: bool,
    ) -> StageResponse:
        """Run a single stage and return the response.

        Args:
            stage: The stage specification dictionary
            continue_on_fail: if True, swallow TavernExceptions and return a
                              failed StageResponse instead of re-raising

        Returns:
            StageResponse with the result of running the stage
        """
        stage = dict(stage)  # Make a copy to avoid mutating the original
        stage_name = stage.get("name", "unnamed-stage")

        default_strictness = StrictLevel.all_on()
        test_spec = {"test_name": "starlark-pipeline", "stages": [stage]}

        runner = _TestRunner(
            default_global_strictness=default_strictness,
            sessions=self._sessions,
            test_block_config=self._test_config,
            test_spec=test_spec,
        )

        try:
            tinctures = get_stage_tinctures(stage, test_spec)
            stage_config = self._test_config.with_strictness(default_strictness)
            response = runner.wrapped_run_stage(stage, stage_config, tinctures)

            return StageResponse(
                success=True,
                response=response,
                request_vars=self._test_config.variables,
                stage_name=stage_name,
            )

        except TavernException as e:
            logger.error("Stage '%s' failed: %s", stage_name, str(e), exc_info=True)
            if not continue_on_fail:
                raise
            return StageResponse(
                success=False,
                response=None,
                request_vars=self._test_config.variables,
                stage_name=stage_name,
            )

    def _create_response_struct(self, stage_response: StageResponse) -> dict[str, Any]:
        """Convert StageResponse to dict that starlark converts to struct."""
        base_dict: dict[str, Any] = {
            "failed": not stage_response.success,
            "success": stage_response.success,
            "request_vars": stage_response.request_vars,
            "stage_name": stage_response.stage_name,
        }
        if stage_response.response is None:
            return base_dict
        elif isinstance(stage_response.response, requests.Response):
            rest_response = stage_response.response
            base_dict.update(
                {
                    "status_code": rest_response.status_code,
                    "body": rest_response.json(),
                    "headers": rest_response.headers,
                    "cookies": rest_response.cookies,
                }
            )
            return base_dict

        raise NotImplementedError(
            f"gRPC, MQTT, etc. are not supported yet. Got {type(stage_response.response)}"
        )

    def _setup_builtins(self, module: Module) -> None:
        """Set up built-in functions available in starlark scripts."""
        for stage_id, stage in self._stage_registry.get_all_stages().items():
            module[stage_id] = stage

        @_wrap_callable
        def run_stage_binding(stage_id: str, continue_on_fail: bool) -> Any:
            """Run a stage by its ID string.

            Args:
                stage_id: The ID of the stage to run
                continue_on_fail: if True, don't re-raise exceptions from stages that fail

            Returns:
                A Starlark struct with status_code, failed, success, response, etc.
            """
            stage = self._stage_registry.get_stage(stage_id)
            if stage is None:
                raise exceptions.StarlarkError(f"Stage with id '{stage_id}' not found")

            if self._test_config is None:
                raise exceptions.StarlarkError("Test config not initialized")

            stage_response = self._run_stage(stage, continue_on_fail)
            return self._create_response_struct(stage_response)

        module.add_callable("__run_stage", run_stage_binding)

        @_wrap_callable
        def include(filename: str) -> dict[str, Any]:
            """Load a YAML file and return its contents.

            Args:
                filename: Path to the YAML file to include

            Returns:
                The parsed YAML contents as a dictionary
            """
            try:
                for directory in get_include_dirs(
                    [pathlib.Path(self.test_path).parent]
                ):
                    abs_filename = os.path.abspath(os.path.join(directory, filename))
                    logger.debug("Trying to include '%s'", abs_filename)
                    if os.access(abs_filename, os.R_OK):
                        return load_single_document_yaml(abs_filename)

                raise ValueError(f"Failed to include '{filename}'")
            except Exception as e:
                logger.error("Failed to include '%s': %s", filename, e)
                raise ValueError(f"Failed to include '{filename}'") from e

        module.add_callable("include", include)

        @_wrap_callable
        def log(s: str) -> None:
            """log a string to stdout."""
            logger.info(s)

        module.add_callable("log", log)
