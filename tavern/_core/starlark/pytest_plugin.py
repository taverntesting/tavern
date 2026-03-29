"""Pytest plugin integration for starlark pipeline files."""

import logging
import os
import pathlib
import typing
from collections.abc import Iterable
from typing import Any, Optional

import pytest
import starlark
from _pytest._code.code import ExceptionInfo, TerminalRepr
from _pytest.nodes import Collector, Item
from starlark import Dialect

from tavern._core import exceptions
from tavern._core.plugins import load_plugins
from tavern._core.pytest import call_hook
from tavern._core.pytest.config import TestConfig
from tavern._core.pytest.error import ReprdError
from tavern._core.pytest.item import BaseTavernItem
from tavern._core.pytest.util import get_option_generic, load_global_cfg
from tavern._core.starlark.starlark_env import setup_starlark_environment

logger: logging.Logger = logging.getLogger(__name__)


class StarlarkItem(BaseTavernItem):
    """A starlark pipeline test item."""

    def __init__(
        self, *, name: str, parent, spec: dict[str, Any], path: pathlib.Path, **kwargs
    ) -> None:
        super().__init__(name=name, parent=parent, spec=spec, path=path, **kwargs)
        self.starlark_runner: Any = None
        self.starlark_script: str = ""

    @property
    def obj(self):
        """Return a fake obj for pytest to inspect."""

        def fakefun():
            pass

        fakefun.__doc__ = self.name
        return fakefun

    @property
    def _obj(self):
        return self.obj

    @property
    def location(self):
        """Get location in file."""
        return (self.path, 0, f"{self.path}::{self.name}")

    def runtest(self) -> None:
        """Run the starlark pipeline test."""
        self.global_cfg = load_global_cfg(self.config)

        load_plugins(self.global_cfg)

        # INTERNAL
        xfail = self.spec.get("_xfail", False)

        try:
            # Load fixture values
            fixture_values = self._load_fixture_values()
            self.global_cfg.variables.update(fixture_values)

            call_hook(
                self.global_cfg,
                "pytest_tavern_beta_before_every_test_run",
                test_dict=self.spec,
                variables=self.global_cfg.variables,
            )

            # Create test spec with empty stages (starlark handles the stages)
            test_spec = dict(self.spec)

            # Run the starlark pipeline
            self.starlark_runner.load_and_run(self.starlark_script, test_spec)

        except exceptions.BadSchemaError:
            if xfail == "verify":
                logger.info("xfailing test while verifying schema")
                self.add_marker(pytest.mark.xfail, True)
            raise
        except exceptions.TavernException as e:
            if isinstance(xfail, dict):
                if msg := xfail.get("run"):
                    if msg not in str(e):
                        raise Exception(
                            f"error message did not match: expected '{msg}', got '{e!s}'"
                        ) from e
                    logger.info("xfailing test when running")
                    self.add_marker(pytest.mark.xfail, True)
                else:
                    logger.warning("internal error checking 'xfail'")
            elif xfail == "run" and not e.is_final:
                logger.info("xfailing test when running")
                self.add_marker(pytest.mark.xfail, True)
            elif xfail == "finally" and e.is_final:
                logger.info("xfailing test when finalising")
                self.add_marker(pytest.mark.xfail, True)

            raise
        else:
            if xfail:
                raise Exception(f"internal: xfail test did not fail '{xfail}'")
        finally:
            call_hook(
                self.global_cfg,
                "pytest_tavern_beta_after_every_test_run",
                test_dict=self.spec,
                variables=self.global_cfg.variables,
            )

    def repr_failure(
        self, excinfo: ExceptionInfo[BaseException], style: str | None = None
    ) -> TerminalRepr | str | ReprdError:
        """Called when self.runtest() raises an exception."""

        if (
            self.config.getini("tavern-use-default-traceback")
            or self.config.getoption("tavern_use_default_traceback")
            or not issubclass(excinfo.type, exceptions.TavernException)
            or issubclass(excinfo.type, exceptions.BadSchemaError)
        ):
            return super().repr_failure(excinfo)

        if style is not None:
            logger.info("Ignoring style '%s", style)

        error = ReprdError(excinfo, self)
        return error

    def reportinfo(self) -> tuple[pathlib.Path, int, str]:
        return (
            self.path,
            0,
            f"{self.path}::{self.name:s}",
        )


class StarlarkFile(pytest.File):
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

    def _generate_items(self) -> typing.Iterator[StarlarkItem]:
        """Generate test items from the starlark file."""
        # Read the starlark script
        script_content = self.path.read_text(encoding="utf-8")

        # Create test config
        test_config = self._create_test_config()

        # Set up the starlark environment
        runner = setup_starlark_environment(test_config, str(self.path))

        # Try to parse the script first to check for syntax errors
        try:
            dialect = Dialect.extended()
            _ = starlark.parse(os.fspath(self.path), script_content, dialect=dialect)
            logger.debug("Successfully parsed starlark script at %s", self.path)
        except starlark.Error as e:
            logger.error("Failed to parse starlark script at %s: %s", self.path, e)
            raise exceptions.BadSchemaError(
                f"Failed to parse starlark script at {self.path}: {e}"
            ) from e

        # TODO: Have a starlark function like "multiple_tests" which allows for multiple tests to be defined in a single script

        # Create a minimal spec for the item
        test_spec: dict[str, Any] = {
            "test_name": f"starlark-pipeline:{self.path.stem}",
            "stages": [],
        }
        test_name = test_spec["test_name"]
        item = StarlarkItem.item_from_parent(
            name=test_name, parent=self, spec=test_spec, path=self.path
        )

        # Store the runner and script for later execution
        item.starlark_runner = runner
        item.starlark_script = script_content

        # Must initialise fixtures before yielding, same as YamlFile
        item.initialise_fixture_attrs()

        yield item

    def collect(self) -> Iterable[Item | Collector]:
        return self._generate_items()


def pytest_collect_file(parent, file_path: pathlib.Path) -> Optional["StarlarkItem"]:
    """Collect starlark pipeline files (*.tavern.star).

    This hook is called by pytest to collect files. It checks if the
    --tavern-experimental-starlark-pipeline flag is enabled and if the file
    matches the starlark pattern.
    """
    # Check if starlark is enabled
    try:
        starlark_enabled = get_option_generic(
            parent.config, "tavern-experimental-starlark-pipeline", False
        )
    except ValueError:
        starlark_enabled = False

    if not starlark_enabled:
        return None

    # Check if this is a starlark pipeline file
    if str(file_path).endswith(".tavern.star"):
        return StarlarkFile.from_parent(parent, path=file_path)

    return None
