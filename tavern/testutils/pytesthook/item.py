import copy
import logging

from _pytest import fixtures
import attr
import pytest

from tavern.core import run_test
from tavern.plugins import load_plugins
from tavern.schemas.files import verify_tests
from tavern.testutils.pytesthook.newhooks import call_hook
from tavern.util import exceptions

from .error import ReprdError
from .util import load_global_cfg

logger = logging.getLogger(__name__)


class YamlItem(pytest.Item):
    """Simple wrapper around new test type that can report errors more
    accurately than the default pytest reporting stuff

    At the time of writing this doesn't print the error very nicely, but it
    should be enough to track down what went wrong

    Attributes:
        path (str): filename that this test came from
        spec (dict): The whole dictionary of the test
    """

    def __init__(self, name, parent, spec, path):
        super(YamlItem, self).__init__(name, parent)
        self.path = path
        self.spec = spec

        self.global_cfg = {}

    def initialise_fixture_attrs(self):
        # pylint: disable=protected-access,attribute-defined-outside-init
        self.funcargs = {}

        # _get_direct_parametrize_args checks parametrize arguments in Python
        # functions, but we don't care about that in Tavern.
        self.session._fixturemanager._get_direct_parametrize_args = lambda _: []

        fixtureinfo = self.session._fixturemanager.getfixtureinfo(
            self, self.obj, type(self), funcargs=False
        )
        self._fixtureinfo = fixtureinfo
        self.fixturenames = fixtureinfo.names_closure
        self._request = fixtures.FixtureRequest(self)

    #     Hack to stop issue with pytest-rerunfailures
    _initrequest = initialise_fixture_attrs

    def setup(self):
        super(YamlItem, self).setup()
        fixtures.fillfixtures(self)

    @property
    def obj(self):
        stages = []
        for i, stage in enumerate(self.spec["stages"]):
            name = "<unknown>"
            if "name" in stage:
                name = stage["name"]
            elif "id" in stage:
                name = stage["id"]
            stages.append("{:d}: {:s}".format(i + 1, name))

        # This needs to be a function or skipif breaks
        def fakefun():
            pass

        fakefun.__doc__ = self.name + ":\n" + "\n".join(stages)
        return fakefun

    def add_markers(self, pytest_marks):
        for pm in pytest_marks:
            if pm.name == "usefixtures":
                # Need to do this here because we expect a list of markers from
                # usefixtures, which pytest then wraps in a tuple. we need to
                # extract this tuple so pytest can use both fixtures.
                if isinstance(pm.mark.args[0], (list, tuple)):
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
            if isinstance(m.args, (list, tuple)):
                mark_values = {f: self.funcargs[f] for f in m.args}
            elif isinstance(m.args, str):
                # Not sure if this can happen if validation is working
                # correctly, but it appears to be slightly broken so putting
                # this check here just in case
                mark_values = {m.args: self.funcargs[m.args]}
            else:
                raise exceptions.BadSchemaError(
                    (
                        "Can't handle 'usefixtures' spec of '{}'."
                        " There appears to be a bug in pykwalify so verification of"
                        " 'usefixtures' is broken - it should be a list of fixture"
                        " names"
                    ).format(m.args)
                )

            if any(mv in values for mv in mark_values):
                logger.warning("Overriding value for %s", mark_values)

            values.update(mark_values)

        return values

    def runtest(self):
        # Do a deep copy because this sometimes still retains things from previous tests(?)
        self.global_cfg = copy.deepcopy(load_global_cfg(self.config))

        self.global_cfg.setdefault("variables", {})

        load_plugins(self.global_cfg)

        self.global_cfg["tavern_internal"] = {"pytest_hook_caller": self.config.hook}

        # INTERNAL
        # NOTE - now that we can 'mark' tests, we could use pytest.mark.xfail
        # instead. This doesn't differentiate between an error in verification
        # and an error when running the test though.
        xfail = self.spec.get("_xfail", False)

        try:
            fixture_values = self._load_fixture_values()
            self.global_cfg["variables"].update(fixture_values)

            call_hook(
                self.global_cfg,
                "pytest_tavern_beta_before_every_test_run",
                test_dict=self.spec,
                variables=self.global_cfg["variables"],
            )

            verify_tests(self.spec)

            run_test(self.path, self.spec, self.global_cfg)
        except exceptions.BadSchemaError:
            if xfail == "verify":
                logger.info("xfailing test while verifying schema")
            else:
                raise
        except exceptions.TavernException:
            if xfail == "run":
                logger.info("xfailing test when running")
            else:
                raise
        else:
            if xfail:
                logger.error("Expected test to fail")
                raise exceptions.TestFailError(
                    "Expected test to fail at {} stage".format(xfail)
                )

    def repr_failure(self, excinfo, style=None):
        """ called when self.runtest() raises an exception.

        By default, will raise a custom formatted traceback if it's a tavern error. if not, will use the default
        python traceback
        """

        if (
            self.config.getini("tavern-use-default-traceback")
            or self.config.getoption("tavern_use_default_traceback")
            or not issubclass(excinfo.type, exceptions.TavernException)
            or issubclass(excinfo.type, exceptions.BadSchemaError)
        ):
            return super(YamlItem, self).repr_failure(excinfo)

        if style is not None:
            logger.info("Ignoring style '%s", style)

        return ReprdError(excinfo, self)

    def reportinfo(self):
        return self.fspath, 0, "{s.path}::{s.name:s}".format(s=self)
