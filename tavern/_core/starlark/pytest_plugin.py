"""Pytest plugin integration for starlark pipeline files."""

import logging
import pathlib
import typing
from typing import Optional

import pytest
import starlark

from tavern._core import exceptions
from tavern._core.pytest.config import TestConfig
from tavern._core.pytest.file import YamlItem
from tavern._core.pytest.util import get_option_generic, load_global_cfg
from tavern._core.starlark.starlark_env import setup_starlark_environment

logger: logging.Logger = logging.getLogger(__name__)


def _add_starlark_parser_option(parser: pytest.Parser) -> None:
    """Add the experimental starlark pipeline command line option."""
    parser.addoption(
        "--experimental-starlark-pipeline",
        action="store_true",
        default=False,
        help="Enable experimental starlark pipeline support (*.tavern.star files)",
    )


pytest_funcs_to_hook = []


def pytest_collect_file(parent, file_path: pathlib.Path) -> Optional["YamlItem"]:
    """Collect starlark pipeline files (*.tavern.star).

    This hook is called by pytest to collect files. It checks if the
    --experimental-starlark-pipeline flag is enabled and if the file
    matches the starlark pattern.
    """
    # Check if starlark is enabled
    try:
        starlark_enabled = get_option_generic(
            parent.config, "experimental_starlark_pipeline", False
        )
    except ValueError:
        starlark_enabled = False

    if not starlark_enabled:
        return None

    # Check if this is a starlark pipeline file
    if str(file_path).endswith(".tavern.star"):
        return StarlarkYamlFile.from_parent(parent, path=file_path)

    return None


class StarlarkYamlFile(pytest.File):
    """A starlark pipeline file that can be executed as a Tavern test."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        class FakeObj:
            __doc__ = str(self.path)

        self.obj = FakeObj

    def _create_test_config(self) -> TestConfig:
        """Create a TestConfig for running starlark pipelines."""

        global_cfg = load_global_cfg(self.config)

        return TestConfig(
            variables=global_cfg.variables.copy(),
            strict=global_cfg.strict,
            follow_redirects=global_cfg.follow_redirects,
            stages=global_cfg.stages,
            tavern_internal=global_cfg.tavern_internal,
        )

    def _generate_items(self) -> typing.Iterator[YamlItem]:
        """Generate test items from the starlark file."""
        # Read the starlark script
        script_content = self.path.read_text(encoding="utf-8")

        # Create test config
        test_config = self._create_test_config()

        # Set up the starlark environment
        runner = setup_starlark_environment(test_config, str(self.path))

        # Try to parse the script first to check for syntax errors
        try:
            from starlark import Dialect

            dialect = Dialect.standard()
            ast = starlark.parse(script_content, dialect=dialect)
            logger.debug("Successfully parsed starlark script at %s", self.path)
        except starlark.Error as e:
            logger.error("Failed to parse starlark script at %s: %s", self.path, e)
            raise exceptions.BadSchemaError(
                f"Failed to parse starlark script at {self.path}: {e}"
            ) from e

        # Create a YamlItem to represent this test
        test_name = f"starlark-pipeline:{self.path.stem}"
        item = YamlItem.yamlitem_from_parent(
            test_name, self, {"test_name": test_name, "stages": []}, self.path
        )

        # Store the runner and script for later execution
        item.starlark_runner = runner
        item.starlark_script = script_content

        yield item


# For backwards compatibility
def pytest_tavern_beta_before_every_request(request_args) -> None:
    """Hook called before every request (no-op for starlark)."""
    pass


def starlark_collect_file(parent, file_path: pathlib.Path):
    """Collect starlark pipeline files.

    Wrapper function to be called from the main pytest plugin.
    """
    # Check if starlark is enabled
    try:
        starlark_enabled = get_option_generic(
            parent.config, "experimental_starlark_pipeline", False
        )
    except ValueError:
        starlark_enabled = False

    if not starlark_enabled:
        return None

    # Check if this is a starlark pipeline file
    if str(file_path).endswith(".tavern.star"):
        return StarlarkYamlFile.from_parent(parent, path=file_path)

    return None
