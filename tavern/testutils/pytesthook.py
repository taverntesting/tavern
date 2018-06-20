import re
import itertools
import logging
import copy
import pytest
import yaml
from future.utils import raise_from

from tavern.plugins import load_plugins
from tavern.core import run_test
from tavern.util.general import load_global_config
from tavern.util import exceptions
from tavern.util.loader import IncludeLoader
from tavern.util.dict_util import format_keys
from tavern.schemas.files import verify_tests


logger = logging.getLogger(__name__)

match_tavern_file = re.compile(r'.+\.tavern\.ya?ml$').match


def pytest_collect_file(parent, path):
    """On collecting files, get any files that end in .tavern.yaml or .tavern.yml as tavern
    test files

    Todo:
        Change this to .tyaml or something?
    """
    if path.basename.startswith("test") and match_tavern_file(path.strpath):
        return YamlFile(path, parent)

    return None


def add_parser_options(parser_addoption, with_defaults=True):
    """Add argparse options

    This is shared between the CLI and pytest (for now)
    """
    parser_addoption(
        "--tavern-global-cfg",
        help="One or more global configuration files to include in every test",
        required=False,
        nargs="+",
    )
    parser_addoption(
        "--tavern-http-backend",
        help="Which http backend to use",
        default='requests' if with_defaults else None,
    )
    parser_addoption(
        "--tavern-mqtt-backend",
        help="Which mqtt backend to use",
        default='paho-mqtt' if with_defaults else None,
    )
    parser_addoption(
        "--tavern-strict",
        help="Default response matching strictness",
        default=None,
        nargs="+",
        choices=["body", "headers", "redirect_query_params"],
    )


def pytest_addoption(parser):
    """Add an option to pass in a global config file for tavern
    """
    add_parser_options(parser.addoption, with_defaults=False)

    parser.addini(
        "tavern-global-cfg",
        help="One or more global configuration files to include in every test",
        type="linelist",
        default=[]
    )
    parser.addini(
        "tavern-http-backend",
        help="Which http backend to use",
        default="requests",
    )
    parser.addini(
        "tavern-mqtt-backend",
        help="Which mqtt backend to use",
        default="paho-mqtt",
    )
    parser.addini(
        "tavern-strict",
        help="Default response matching strictness",
        type="args",
        default=None,
    )


class YamlFile(pytest.File):

    """Custom `File` class that loads each test block as a different test
    """

    def __init__(self, *args, **kwargs):
        super(YamlFile, self).__init__(*args, **kwargs)

        # This (and the FakeObj below) are to make pytest-pspec not error out.
        # The 'doctstring' for this is the filename, the 'docstring' for each
        # individual test is the actual test name.
        class FakeObj(object):
            __doc__ = self.fspath

        self.obj = FakeObj

    def get_parametrized_items(self, test_spec, parametrize_marks, pytest_marks):
        """Return new items with new format values available based on the mark

        This will change the name from something like 'test a thing' to 'test a
        thing[param1]', 'test a thing[param2]', etc. This probably messes with
        -k

        Note:
            This still has the pytest.mark.parametrize mark on it, though it
            doesn't appear to do anything. This could be removed?
        """

        # These should be in the same order as specified in the input file
        vals = [i["parametrize"]["vals"] for i in parametrize_marks]

        try:
            combined = itertools.product(*vals)
        except TypeError:
            # HACK
            # This is mainly to get around Python 2 limitations (which we should
            # stop supporting!!). If the input is invalid, then this will raise
            # a typerror, which is then raised below when verify_tests is
            # called. We can just raise an error during collection, but the
            # error on Python 2 is completely useless because it has no
            # 'raise x from y' syntax for exception causes. This will still
            # raise an error at validation, but the test name will be a bit
            # mangled
            vals = [["TAVERNERR"]]
            combined = itertools.product(*vals)

        keys = [i["parametrize"]["key"] for i in parametrize_marks]

        # Use for formatting parametrized values - eg {}-{}, {}-{}-{}, etc.
        inner_fmt = "-".join(["{}"]*len(keys))

        for v in combined:
            inner_formatted = inner_fmt.format(*v)

            spec_new = copy.deepcopy(test_spec)

            # Change the name
            spec_new["test_name"] = test_spec["test_name"] + "[{}]".format(inner_formatted)

            # Make this new thing available for formatting
            spec_new["includes"].append({
                "name": "parametrized[{}]".format(inner_formatted),
                "description": "autogenerated by Tavern",
                "variables": {
                    k: v for k, v in zip(keys, v)
                }
            })
            # And create the new item
            item_new = YamlItem(spec_new["test_name"], self, spec_new, self.fspath)

            for pm in pytest_marks:
                # All other marks should be added to this too
                item_new.add_marker(pm)

            yield item_new

    def _generate_items(self, test_spec):

        item = YamlItem(test_spec["test_name"], self, test_spec, self.fspath)

        marks = test_spec.get("marks", [])

        if marks:
            # Get included variables so we can do things like:
            # skipif: {my_integer} > 2
            # skipif: 'https' in '{hostname}'
            # skipif: '{hostname}'.contains('ignoreme')
            included = test_spec.get("includes", [])
            fmt_vars = {}
            for i in included:
                fmt_vars.update(**i.get("variables", {}))

            pytest_marks = []

            # This should either be a string or a skipif
            for m in marks:
                if isinstance(m, str):
                    m = format_keys(m, fmt_vars)
                    pytest_marks.append(getattr(pytest.mark, m))
                elif isinstance(m, dict):
                    for markname, extra_arg in m.items():
                        # NOTE
                        # cannot do 'skipif' and rely on a parametrized
                        # argument.
                        extra_arg = format_keys(extra_arg, fmt_vars)
                        pytest_marks.append(getattr(pytest.mark, markname)(extra_arg))

            # Do this after we've added all the other marks so doing
            # things like selecting on mark names still works even
            # after parametrization
            parametrize_marks = [i for i in marks if isinstance(i, dict) and "parametrize" in i]
            if parametrize_marks:
                # no 'yield from' in python 2...
                for new_item in self.get_parametrized_items(
                    test_spec,
                    parametrize_marks,
                    pytest_marks
                ):
                    yield new_item

                # Only yield the parametrized ones
                return

            for pm in pytest_marks:
                item.add_marker(pm)

        yield item

    def collect(self):
        """Load each document in the given input file into a different test

        Yields:
            YamlItem: Essentially an individual pytest 'test object'
        """
        # pylint: disable=too-many-nested-blocks

        # pylint: disable=too-many-locals

        try:
            # Convert to a list so we can catch parser exceptions
            all_tests = list(yaml.load_all(self.fspath.open(encoding="utf-8"), Loader=IncludeLoader))
        except yaml.parser.ParserError as e:
            raise_from(exceptions.BadSchemaError, e)

        for test_spec in all_tests:
            if not test_spec:
                logger.warning("Empty document in input file '%s'", self.fspath)
                continue

            try:
                for i in self._generate_items(test_spec):
                    yield i
            except (TypeError, KeyError):
                verify_tests(test_spec, load_plugins=False)
                raise


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

    @property
    def obj(self):
        stages = ["{:d}: {:s}".format(i + 1, stage["name"]) for i, stage in enumerate(self.spec["stages"])]

        # This needs to be a function or skipif breaks
        def fakefun():
            pass

        fakefun.__doc__ = self.name + ":\n" + "\n".join(stages)
        self.obj = fakefun

    def runtest(self):
        # Load ini first
        ini_global_cfg_paths = self.config.getini("tavern-global-cfg") or []
        # THEN load command line, to allow overwriting of values
        cmdline_global_cfg_paths = self.config.getoption("tavern_global_cfg") or []

        all_paths = ini_global_cfg_paths + cmdline_global_cfg_paths
        global_cfg = load_global_config(all_paths)

        if self.config.getini("tavern-strict") is not None:
            strict = self.config.getini("tavern-strict")
            if isinstance(strict, list):
                if any(i not in ["body", "headers", "redirect_query_params"] for i in strict):
                    raise exceptions.UnexpectedKeysError("Invalid values for 'strict' use in config file")
        elif self.config.getoption("tavern_strict") is not None:
            strict = self.config.getoption("tavern_strict")
        else:
            strict = []

        global_cfg["strict"] = strict

        global_cfg["backends"] = {}
        backends = ["http", "mqtt"]
        for b in backends:
            # similar logic to above - use ini, then cmdline if present
            ini_opt = self.config.getini("tavern-{}-backend".format(b))
            cli_opt = self.config.getoption("tavern_{}_backend".format(b))

            in_use = ini_opt
            if cli_opt and (cli_opt != ini_opt):
                in_use = cli_opt

            global_cfg["backends"][b] = in_use

        load_plugins(global_cfg)

        # INTERNAL
        # NOTE - now that we can 'mark' tests, we could use pytest.mark.xfail
        # instead. This doesn't differentiate between an error in verification
        # and an error when running the test though.
        xfail = self.spec.get("_xfail", False)

        try:
            verify_tests(self.spec)
            run_test(self.path, self.spec, global_cfg)
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
                raise exceptions.TestFailError

    def repr_failure(self, excinfo): # pylint: disable=no-self-use
        """ called when self.runtest() raises an exception.

        Todo:
            This stuff is copied from pytest at the moment - needs a bit of
            modifying so that it shows the yaml and all the reasons the test
            failed rather than a traceback
        """

        if not issubclass(excinfo.type, exceptions.TavernException):
            return super(YamlItem, self).repr_failure(excinfo)

        return super(YamlItem, self).repr_failure(excinfo)

    def reportinfo(self):
        # pylint: disable=missing-format-attribute
        return self.fspath, 0, "{self.path}::{self.name:s}".format(self=self)
