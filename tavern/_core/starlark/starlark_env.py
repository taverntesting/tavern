"""Starlark environment setup for Tavern pipelines."""

import dataclasses
import functools
import logging
import os
import pathlib
from contextlib import ExitStack
from typing import Any, TypedDict

import starlark
from starlark import Dialect, Globals, Module

from tavern._core import exceptions
from tavern._core.exceptions import TavernException
from tavern._core.loader import get_include_dirs, load_single_document_yaml
from tavern._core.pytest.config import TestConfig
from tavern._core.run import _TestRunner, get_extra_sessions
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
    response: dict[str, Any]
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


def _run_stage(
    stage: dict[str, Any],
    test_config: TestConfig,
    sessions: dict[str, Any] | None = None,
) -> StageResponse:
    """Run a single stage and return the response.

    Args:
        stage: The stage specification dictionary
        test_config: The test configuration with available variables
        sessions: Optional dictionary of session contexts to use for the stage.
                  If None, creates an empty sessions dict.

    Returns:
        StageResponse with the result of running the stage
    """
    stage = dict(stage)  # Make a copy to avoid mutating the original
    stage_name = stage.get("name", "unnamed-stage")

    # Get default strictness (use all_on as default)
    default_strictness = StrictLevel.all_on()

    # Create a minimal test spec
    test_spec = {"test_name": "starlark-pipeline", "stages": [stage]}

    # Use provided sessions or create empty dict
    if sessions is None:
        sessions = {}

    # Create runner
    runner = _TestRunner(
        default_global_strictness=default_strictness,
        sessions=sessions,
        test_block_config=test_config,
        test_spec=test_spec,
    )

    try:
        # Get tinctures for this stage
        tinctures = get_stage_tinctures(stage, test_spec)

        # Create stage config with strictness
        stage_config = test_config.with_strictness(default_strictness)

        # Run the stage using the internal wrapped method
        runner.wrapped_run_stage(stage, stage_config, tinctures)

        # If we get here, the stage succeeded
        # IMPORTANT: test_config has been mutated - capture the updated variables
        response_dict = _extract_response_data(stage)

        return StageResponse(
            success=True,
            response=response_dict,
            request_vars=test_config.variables,
            stage_name=stage_name,
        )

    except TavernException as e:
        # Only catch tavern exceptions here - any other exception should be raised
        logger.warning("Stage '%s' failed: %s", stage_name, str(e))
        # Even on failure, test_config may have partial updates
        return StageResponse(
            success=False,
            response={"error": str(e)},
            request_vars=test_config.variables,
            stage_name=stage_name,
        )


def _extract_response_data(stage: dict[str, Any]) -> dict[str, Any]:
    """Extract relevant response data from a stage for starlark.

    This is a helper to create a JSON-serializable dictionary from
    the stage specification that can be inspected in starlark.
    """
    response_block = stage.get("response", {})

    # Return the response spec that was defined
    # The actual response will come from the HTTP call
    return {
        "expected_status": response_block.get("status_code"),
        "has_json_expectation": "json" in response_block,
        "has_header_expectations": "headers" in response_block,
        "has_cookie_expectations": "cookies" in response_block,
    }


class StarlarkPipelineRunner:
    """Runner for executing starlark pipeline scripts.

    This class handles loading and executing starlark scripts that can
    control the flow of test execution.
    """

    def __init__(self, test_path: str, stages: list[dict] | None = None):
        """Initialize the pipeline runner.

        Args:
            test_path: Path to the .tavern.star file being run
            stages: Optional list of stage dictionaries to register
        """
        self.test_path = test_path
        self.globals = Globals.standard().extended_by(
            [
                starlark.LibraryExtension.StructType,
            ]
        )
        self.sessions: dict[str, Any] = {}
        self._stage_registry = StageRegistry(stages) if stages else StageRegistry([])
        self._test_config: TestConfig | None = None
        self._sessions: dict[str, Any] | None = None

    def load_and_run(
        self, test_config: TestConfig, script: str, test_spec: dict[str, Any]
    ) -> Any:
        """Load and run a starlark pipeline script.

        Args:
            test_config: The test configuration with variables
            script: The starlark script content
            test_spec: The test specification dictionary

        Returns:
            The return value of the script, if any
        """
        stages = test_spec.get("stages", [])
        self._stage_registry = StageRegistry(stages)
        self._test_config = test_config
        self._sessions = {}

        # Create the starlark module
        module = Module()

        test_config.variables.pop("event_loop_policy")
        test_config.variables.pop("_session_faker")

        # Add built-in functions to module
        self._setup_builtins(module)

        # Parse the script
        dialect = Dialect.extended()

        try:
            ast = starlark.parse(str(self.test_path), script, dialect=dialect)
        except starlark.Error as e:
            logger.error("Failed to parse starlark script: %s", e)
            raise ValueError("Failed to parse starlark script") from e

        # Use ExitStack to manage session context like in run.py
        with ExitStack() as stack:
            self.sessions = get_extra_sessions(test_spec, test_config)
            self._sessions = self.sessions

            for name, session in self.sessions.items():
                logger.debug("Entering context for %s", name)
                stack.enter_context(session)

            # Evaluate the script
            try:
                starlark.eval(module, ast, self.globals)  # type: ignore[arg-type]
                result = module.freeze().call("run_pipeline")
            except starlark.StarlarkError as e:
                logger.error("Failed to evaluate starlark script: %s", e)
                raise RuntimeError("Failed to evaluate starlark script") from e

        return result

    def run_stage(self, stage_id: str) -> Any:
        """Run a stage by its ID string.

        Args:
            stage_id: The ID of the stage to run

        Returns:
            A Starlark struct with status_code, failed, success, response, etc.
        """
        stage = self._stage_registry.get_stage(stage_id)
        if stage is None:
            raise exceptions.StarlarkError(f"Stage with id '{stage_id}' not found")

        if self._test_config is None:
            raise exceptions.StarlarkError("Test config not initialized")

        stage_response = _run_stage(stage, self._test_config, self._sessions)
        return self._create_response_struct(stage_response)

    def _create_response_struct(self, stage_response: StageResponse) -> Any:
        """Convert StageResponse to Starlark struct."""
        response_data = stage_response.response
        return starlark.struct(
            status_code=response_data.get("status_code", 0),
            failed=not stage_response.success,
            success=stage_response.success,
            body=response_data.get("body"),
            headers=response_data.get("headers", {}),
            cookies=response_data.get("cookies", {}),
            request_vars=stage_response.request_vars,
            stage_name=stage_response.stage_name,
        )

    def _create_run_stage_binding(self):
        @_wrap_callable
        def run_stage_binding(stage_id: str) -> Any:
            return self.run_stage(stage_id)

        return run_stage_binding

    def _setup_builtins(self, module: Module) -> None:
        """Set up built-in functions available in starlark scripts."""
        for stage_id, stage in self._stage_registry.get_all_stages().items():
            module.set(stage_id, stage)

        module.add_callable("run_stage", self._create_run_stage_binding())

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
