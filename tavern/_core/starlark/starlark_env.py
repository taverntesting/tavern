"""Starlark environment setup for Tavern pipelines."""

import logging
from typing import Any

import starlark
from starlark import Dialect, Module

from tavern._core.loader import load_single_document_yaml
from tavern._core.pytest.config import TestConfig
from tavern._core.starlark.runner import StageResponse

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
        self.globals: dict[str, Any] = {}

    def load_and_run(self, script: str) -> Any:
        """Load and run a starlark pipeline script.

        Args:
            script: The starlark script content

        Returns:
            The return value of the script, if any
        """
        # Create the starlark module
        module = Module()

        # Set up globals with builtin functions
        self.globals = {"global": {}}

        # Add built-in functions
        self._setup_builtins(module.globals)

        # Add include function
        self._setup_include(module.globals)

        # Add run_stage function
        self._setup_run_stage(module.globals)

        # Add fail function
        self._setup_fail(module.globals)

        # Parse the script
        dialect = Dialect.standard()

        try:
            ast = starlark.parse(script, dialect=dialect)
        except starlark.Error as e:
            logger.error("Failed to parse starlark script: %s", e)
            raise ValueError(f"Failed to parse starlark script: {e}") from e

        # Evaluate the script
        try:
            result = starlark.eval(ast, self.globals, module=module)
        except starlark.StarlarkError as e:
            logger.error("Failed to evaluate starlark script: %s", e)
            raise RuntimeError(f"Failed to evaluate starlark script: {e}") from e

        return result

    def _setup_builtins(self, globals: dict[str, Any]) -> None:
        """Set up built-in functions available in starlark scripts."""

    def _setup_include(self, globals: dict[str, Any]) -> None:
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

        globals["include"] = include

    def _setup_run_stage(self, globals: dict[str, Any]) -> None:
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
            return run_stage(stage, self.test_config)

        globals["run_stage"] = run_stage

    def _setup_fail(self, globals: dict[str, Any]) -> None:
        """Set up the fail function (also added in _setup_builtins for consistency)."""
        # Already added in _setup_builtins, but kept for explicit hiding
        pass


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
