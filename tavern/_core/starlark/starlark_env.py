"""Starlark environment setup for Tavern pipelines."""

import logging
from contextlib import ExitStack
from typing import Any

import starlark
from starlark import Dialect, Globals, Module

from tavern._core.loader import load_single_document_yaml
from tavern._core.pytest.config import TestConfig
from tavern._core.starlark.runner import StageResponse
from tavern._core.starlark.runner import run_stage as _run_stage

logger: logging.Logger = logging.getLogger(__name__)


class StarlarkPipelineRunner:
    """Runner for executing starlark pipeline scripts.

    This class handles loading and executing starlark scripts that can
    control the flow of test execution.
    """

    def __init__(self, test_config: TestConfig, test_path: str):
        """Initialize the pipeline runner.

        Args:
            test_config: The test configuration with variables
            test_path: Path to the .tavern.star file being run
        """
        self.test_config = test_config
        self.test_path = test_path
        self.globals = Globals.standard()
        self.sessions: dict[str, Any] = {}

    def get_sessions(self, test_spec: dict[str, Any]) -> dict[str, Any]:
        """Get extra sessions from test spec.

        This mirrors the logic in tavern/_core/run.py for getting sessions.
        """
        from tavern._core.run import get_extra_sessions

        return get_extra_sessions(test_spec, self.test_config)

    def load_and_run(self, script: str, test_spec: dict[str, Any]) -> Any:
        """Load and run a starlark pipeline script.

        Args:
            script: The starlark script content
            test_spec: The test specification dictionary

        Returns:
            The return value of the script, if any
        """
        # Create the starlark module
        module = Module()

        # Add built-in functions to module
        self._setup_builtins(module)

        # Add include function
        self._setup_include(module)

        # Add run_stage function
        self._setup_run_stage(module)

        # Add fail function
        self._setup_fail(module)

        # Parse the script
        dialect = Dialect.standard()

        try:
            ast = starlark.parse(str(self.test_path), script, dialect=dialect)
        except starlark.Error as e:
            logger.error("Failed to parse starlark script: %s", e)
            raise ValueError(f"Failed to parse starlark script: {e}") from e

        # Use ExitStack to manage session context like in run.py
        with ExitStack() as stack:
            self.sessions = self.get_sessions(test_spec)

            for name, session in self.sessions.items():
                logger.debug("Entering context for %s", name)
                stack.enter_context(session)

            # Evaluate the script
            try:
                result = starlark.eval(module, ast, self.globals)  # type: ignore[arg-type]
            except starlark.StarlarkError as e:
                logger.error("Failed to evaluate starlark script: %s", e)
                raise RuntimeError(f"Failed to evaluate starlark script: {e}") from e

        return result

    def _setup_builtins(self, module: Module) -> None:
        """Set up built-in functions available in starlark scripts."""

    def _setup_include(self, module: Module) -> None:
        """Set up the include function for loading YAML files."""

        def include(filename: str) -> dict[str, Any]:
            """Load a YAML file and return its contents.

            Args:
                filename: Path to the YAML file to include

            Returns:
                The parsed YAML contents as a dictionary
            """
            try:
                return load_single_document_yaml(filename)
            except Exception as e:
                logger.error("Failed to include '%s': %s", filename, e)
                raise ValueError(f"Failed to include '{filename}': {e}") from e

        module.add_callable("include", include)

    def _setup_run_stage(self, module: Module) -> None:
        """Set up the run_stage function for executing test stages."""

        def run_stage(stage: dict[str, Any]) -> StageResponse:
            """Run a single test stage and return the response.

            Args:
                stage: A dictionary containing the stage specification
                   - name: Human readable name
                   - request: Request specification (url, method, etc.)
                   - response: Expected response (status_code, etc.)

            Returns:
                StageResponse with success/failure and response data
            """
            return _run_stage(stage, self.test_config, self.sessions)

        module.add_callable("run_stage", run_stage)

    def _setup_fail(self, module: Module) -> None:
        """Set up the fail function to stop execution."""

        def fail(msg: str = "test failed") -> None:
            """Stop execution immediately with an optional message.

            Args:
                msg: Optional message describing why execution stopped
            """
            raise RuntimeError(msg)

        module.add_callable("fail", fail)


def setup_starlark_environment(
    test_config: TestConfig,
    test_path: str,
) -> StarlarkPipelineRunner:
    """Set up a starlark environment for running pipeline scripts.

    Args:
        test_config: The test configuration with variables
        test_path: Path to the .tavern.star file being run

    Returns:
        A StarlarkPipelineRunner instance ready to execute scripts
    """
    return StarlarkPipelineRunner(test_config, test_path)
