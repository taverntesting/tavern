import logging
import pathlib
from collections.abc import MutableMapping
from typing import Optional, Union

import attr
import pytest
import yaml
from _pytest._code.code import ExceptionInfo, TerminalRepr
from _pytest.nodes import Node

from tavern._core import exceptions
from tavern._core.loader import error_on_empty_scalar
from tavern._core.plugins import load_plugins
from tavern._core.pytest import call_hook
from tavern._core.pytest.error import ReprdError
from tavern._core.report import attach_text
from tavern._core.run import run_test
from tavern._core.schema.files import verify_tests

from .config import TestConfig
from .util import load_global_cfg

logger: logging.Logger = logging.getLogger(__name__)


class YamlItem(pytest.Item):
    """Simple wrapper around new test type that can report errors more
    accurately than the default pytest reporting stuff

    At the time of writing this doesn't print the error very nicely, but it
    should be enough to track down what went wrong

    Attributes:
        path: filename that this test came from
        spec: The whole dictionary of the test
        global_cfg: configuration for test
    """

    # See https://github.com/taverntesting/tavern/issues/825
    _patched_yaml = False

    global_cfg: TestConfig

    def __init__(
        self, *, name: str, parent, spec: MutableMapping, path: pathlib.Path, **kwargs
    ) -> None:
        if "grpc" in spec:
            logger.warning("Tavern grpc support is in an experimental stage")

        super().__init__(name, parent, **kwargs)
        self.path = path
        self.spec = spec

        if not YamlItem._patched_yaml:
            yaml.parser.Parser.process_empty_scalar = (  # type:ignore
                error_on_empty_scalar
            )

            YamlItem._patched_yaml = True

    @classmethod
    def yamlitem_from_parent(cls, name, parent: Node, spec, path: pathlib.Path):
        return cls.from_parent(parent, name=name, spec=spec, path=path)

    def initialise_fixture_attrs(self) -> None:
        self.funcargs = {}  # type: ignore

        # _get_direct_parametrize_args checks parametrize arguments in Python
        # functions, but we don't care about that in Tavern.
        self.session._fixturemanager._get_direct_parametrize_args = (  # type: ignore
            lambda _: []  # type: ignore
        )  # type: ignore

        fixtureinfo = self.session._fixturemanager.getfixtureinfo(
            self, self.obj, type(self), funcargs=False
        )
        self._fixtureinfo = fixtureinfo
        self.fixturenames = fixtureinfo.names_closure
        self._request = pytest.FixtureRequest(self, _ispytest=True)

    @property
    def location(self):
        """get location in file"""
        location = super().location
        location = (location[0], self.spec.start_mark.line, location[2])
        return location

    #     Hack to stop issue with pytest-rerunfailures
    _initrequest = initialise_fixture_attrs

    def setup(self) -> None:
        super().setup()
        self._request._fillfixtures()

    @property
    def obj(self):
        stages = []
        for i, stage in enumerate(self.spec["stages"]):
            name = "<unknown>"
            if "name" in stage:
                name = stage["name"]
            elif "id" in stage:
                name = stage["id"]
            stages.append(f"{i + 1:d}: {name:s}")

        # This needs to be a function or skipif breaks
        def fakefun():
            pass

        fakefun.__doc__ = self.name + ":\n" + "\n".join(stages)
        return fakefun

    @property
    def _obj(self):
        return self.obj

    def add_markers(self, pytest_marks) -> None:
        for pm in pytest_marks:
            if pm.name == "usefixtures":
                if not isinstance(pm.mark.args, list | tuple) or len(pm.mark.args) == 0:
                    logger.error(
                        "'usefixtures' was an invalid type (should"
                        " be a list of fixture names)"
                    )
                    continue
                # Need to do this here because we expect a list of markers from
                # usefixtures, which pytest then wraps in a tuple. we need to
                # extract this tuple so pytest can use both fixtures.
                if isinstance(pm.mark.args[0], list | tuple):
                    new_mark = attr.evolve(pm.mark, args=pm.mark.args[0])
                    pm = attr.evolve(pm, mark=new_mark)
                elif isinstance(pm.mark.args[0], (dict)):
                    # We could raise a TypeError here instead, but then it's a
                    # failure at collection time (which is a bit annoying to
                    # deal with). Instead just don't add the marker and it will
                    # raise an exception at test verification.
                    logger.error(
                        "'usefixtures' was an invalid type (should"
                        " be a list of fixture names)"
                    )
                    continue

            self.add_marker(pm)

    def _load_fixture_values(self):
        fixture_markers = self.iter_markers("usefixtures")

        values = {}

        for m in fixture_markers:
            if isinstance(m.args, list | tuple):
                mark_values = {f: self.funcargs[f] for f in m.args}
            elif isinstance(m.args, str):
                # Not sure if this can happen if validation is working
                # correctly, but it appears to be slightly broken so putting
                # this check here just in case
                mark_values = {m.args: self.funcargs[m.args]}
            else:
                raise exceptions.BadSchemaError(
                    f"Can't handle 'usefixtures' spec of '{m.args}'."
                    " There appears to be a bug in pykwalify so verification of"
                    " 'usefixtures' is broken - it should be a list of fixture"
                    " names"
                )

            if any(mv in values for mv in mark_values):
                logger.warning("Overriding value for %s", mark_values)

            values.update(mark_values)

        # Use autouse fixtures as well
        for name in self.fixturenames:
            if name in values:
                logger.debug("%s already explicitly used", name)
                continue

            mark_values = {name: self.funcargs[name]}
            values.update(mark_values)

        return values

    def runtest(self) -> None:
        self.global_cfg = load_global_cfg(self.config)

        load_plugins(self.global_cfg)

        # INTERNAL
        xfail = self.spec.get("_xfail", False)

        try:
            fixture_values = self._load_fixture_values()
            self.global_cfg.variables.update(fixture_values)

            call_hook(
                self.global_cfg,
                "pytest_tavern_beta_before_every_test_run",
                test_dict=self.spec,
                variables=self.global_cfg.variables,
            )

            verify_tests(self.spec)

            for stage in self.spec["stages"]:
                if not stage.get("name"):
                    if not stage.get("id"):
                        # Should never actually reach here, should be caught at schema check time
                        raise exceptions.BadSchemaError(
                            "One of name or ID must be specified"
                        )

                    stage["name"] = stage["id"]

            run_test(self.path, self.spec, self.global_cfg)

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
        self, excinfo: ExceptionInfo[BaseException], style: Optional[str] = None
    ) -> Union[TerminalRepr, str, ReprdError]:
        """called when self.runtest() raises an exception.

        By default, will raise a custom formatted traceback if it's a tavern error. if not, will use the default
        python traceback
        """

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
        attach_text(str(error), name="error_output")
        return error

    def reportinfo(self) -> tuple[pathlib.Path, int, str]:
        return (
            self.path,
            0,
            f"{self.path}::{self.name:s}",
        )
