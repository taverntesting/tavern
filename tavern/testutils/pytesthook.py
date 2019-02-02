import copy
import io
import itertools
import logging
import os
import re
from builtins import str as ustr

try:
    from functools import lru_cache
except ImportError:
    from backports.functools_lru_cache import lru_cache

import py
import attr
import pytest
import yaml
from _pytest import fixtures
from _pytest._code.code import FormattedExcinfo
from future.utils import raise_from

from box import Box
from tavern.core import run_test
from tavern.plugins import load_plugins
from tavern.schemas.files import verify_tests
from tavern.util import exceptions
from tavern.util.dict_util import format_keys
from tavern.util.general import load_global_config
from tavern.util.loader import IncludeLoader

logger = logging.getLogger(__name__)

match_tavern_file = re.compile(r".+\.tavern\.ya?ml$").match


@lru_cache()
def load_global_cfg(pytest_config):
    """Load globally included config files from cmdline/cfg file arguments

    Args:
        pytest_config (pytest.Config): Pytest config object

    Returns:
        dict: variables/stages/etc from global config files

    Raises:
        exceptions.UnexpectedKeysError: Invalid settings in one or more config
            files detected
    """
    # Load ini first
    ini_global_cfg_paths = pytest_config.getini("tavern-global-cfg") or []
    # THEN load command line, to allow overwriting of values
    cmdline_global_cfg_paths = pytest_config.getoption("tavern_global_cfg") or []

    all_paths = ini_global_cfg_paths + cmdline_global_cfg_paths
    global_cfg = load_global_config(all_paths)

    try:
        loaded_variables = global_cfg["variables"]
    except KeyError:
        logger.debug("Nothing to format in global config files")
    else:
        tavern_box = Box({"tavern": {"env_vars": dict(os.environ)}})

        global_cfg["variables"] = format_keys(loaded_variables, tavern_box)

    if pytest_config.getini("tavern-strict") is not None:
        strict = pytest_config.getini("tavern-strict")
        if isinstance(strict, list):
            if any(
                i not in ["body", "headers", "redirect_query_params"] for i in strict
            ):
                raise exceptions.UnexpectedKeysError(
                    "Invalid values for 'strict' use in config file"
                )
    elif pytest_config.getoption("tavern_strict") is not None:
        strict = pytest_config.getoption("tavern_strict")
    else:
        strict = []

    global_cfg["strict"] = strict

    global_cfg["backends"] = {}
    backends = ["http", "mqtt"]
    for b in backends:
        # similar logic to above - use ini, then cmdline if present
        ini_opt = pytest_config.getini("tavern-{}-backend".format(b))
        cli_opt = pytest_config.getoption("tavern_{}_backend".format(b))

        in_use = ini_opt
        if cli_opt and (cli_opt != ini_opt):
            in_use = cli_opt

        global_cfg["backends"][b] = in_use

    logger.debug("Global config: %s", global_cfg)

    return global_cfg


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
        default="requests" if with_defaults else None,
    )
    parser_addoption(
        "--tavern-mqtt-backend",
        help="Which mqtt backend to use",
        default="paho-mqtt" if with_defaults else None,
    )
    parser_addoption(
        "--tavern-strict",
        help="Default response matching strictness",
        default=None,
        nargs="+",
        choices=["body", "headers", "redirect_query_params"],
    )
    parser_addoption(
        "--tavern-beta-new-traceback",
        help="Use new traceback style (beta)",
        default=False,
        action="store_true",
    )


def pytest_addoption(parser):
    """Add an option to pass in a global config file for tavern
    """
    add_parser_options(parser.addoption, with_defaults=False)

    parser.addini(
        "tavern-global-cfg",
        help="One or more global configuration files to include in every test",
        type="linelist",
        default=[],
    )
    parser.addini(
        "tavern-http-backend", help="Which http backend to use", default="requests"
    )
    parser.addini(
        "tavern-mqtt-backend", help="Which mqtt backend to use", default="paho-mqtt"
    )
    parser.addini(
        "tavern-strict",
        help="Default response matching strictness",
        type="args",
        default=None,
    )
    parser.addini(
        "tavern-beta-new-traceback",
        help="Use new traceback style (beta)",
        type="bool",
        default=False,
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

        # pylint: disable=too-many-locals

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

        for vals_combination in combined:
            # combination of keys and the values they correspond to
            joined = zip(keys, vals_combination)
            flattened_values = []
            variables = {}
            for pair in joined:
                key, value = pair
                # NOTE: If test is invalid, test names generated here will be
                # very weird looking
                if isinstance(key, (str, ustr)):
                    variables[key] = value
                    flattened_values += [value]
                else:
                    for subkey, subvalue in zip(key, value):
                        variables[subkey] = subvalue
                        flattened_values += [subvalue]

            logger.debug("Variables for this combination: %s", variables)

            # Use for formatting parametrized values - eg {}-{}, {}-{}-{}, etc.
            inner_fmt = "-".join(["{}"] * len(flattened_values))

            # Change the name
            inner_formatted = inner_fmt.format(*flattened_values)
            spec_new = copy.deepcopy(test_spec)
            spec_new["test_name"] = test_spec["test_name"] + "[{}]".format(
                inner_formatted
            )

            logger.debug("New test name: %s", spec_new["test_name"])

            # Make this new thing available for formatting
            spec_new.setdefault("includes", []).append(
                {
                    "name": "parametrized[{}]".format(inner_formatted),
                    "description": "autogenerated by Tavern",
                    "variables": variables,
                }
            )
            # And create the new item
            item_new = YamlItem(spec_new["test_name"], self, spec_new, self.fspath)
            item_new.add_markers(pytest_marks)

            yield item_new

    def _get_test_fmt_vars(self, test_spec):
        """Get any format variables that can be inferred for the test at this point

        Args:
            test_spec (dict): Test specification, possibly with included config files

        Returns:
            dict: available format variables
        """
        # Get included variables so we can do things like:
        # skipif: {my_integer} > 2
        # skipif: 'https' in '{hostname}'
        # skipif: '{hostname}'.contains('ignoreme')
        fmt_vars = {}

        global_cfg = load_global_cfg(self.config)
        fmt_vars.update(**global_cfg.get("variables", {}))

        included = test_spec.get("includes", [])
        for i in included:
            fmt_vars.update(**i.get("variables", {}))

        # Needed if something in a config file uses tavern.env_vars
        tavern_box = Box({"tavern": {"env_vars": dict(os.environ)}})

        try:
            fmt_vars = format_keys(fmt_vars, tavern_box)
        except exceptions.MissingFormatError as e:
            # eg, if we have {tavern.env_vars.DOESNT_EXIST}
            msg = "Tried to use tavern format variable that did not exist"
            raise_from(exceptions.MissingFormatError(msg), e)

        return fmt_vars

    def _generate_items(self, test_spec):
        """Modify or generate tests based on test spec

        If there are any 'parametrize' marks, this will generate extra tests
        based on the values

        Args:
            test_spec (dict): Test specification

        Yields:
            YamlItem: Tavern YAML test
        """
        item = YamlItem(test_spec["test_name"], self, test_spec, self.fspath)

        original_marks = test_spec.get("marks", [])

        if original_marks:
            fmt_vars = self._get_test_fmt_vars(test_spec)
            pytest_marks = []
            formatted_marks = []

            for m in original_marks:
                if isinstance(m, str):
                    # a normal mark
                    m = format_keys(m, fmt_vars)
                    pytest_marks.append(getattr(pytest.mark, m))
                elif isinstance(m, dict):
                    # skipif or parametrize (for now)
                    for markname, extra_arg in m.items():
                        # NOTE
                        # cannot do 'skipif' and rely on a parametrized
                        # argument.
                        try:
                            extra_arg = format_keys(extra_arg, fmt_vars)
                        except exceptions.MissingFormatError as e:
                            msg = "Tried to use mark '{}' (with value '{}') in test '{}' but one or more format variables was not in any configuration file used by the test".format(
                                markname, extra_arg, test_spec["test_name"]
                            )
                            # NOTE
                            # we could continue and let it fail in the test, but
                            # this gives a better indication of what actually
                            # happened (even if it is difficult to test)
                            raise_from(exceptions.MissingFormatError(msg), e)
                        else:
                            pytest_marks.append(
                                getattr(pytest.mark, markname)(extra_arg)
                            )
                            formatted_marks.append({markname: extra_arg})

            # Do this after we've added all the other marks so doing
            # things like selecting on mark names still works even
            # after parametrization
            parametrize_marks = [
                i for i in formatted_marks if isinstance(i, dict) and "parametrize" in i
            ]
            if parametrize_marks:
                # no 'yield from' in python 2...
                for new_item in self.get_parametrized_items(
                    test_spec, parametrize_marks, pytest_marks
                ):
                    yield new_item

                # Only yield the parametrized ones
                return

            item.add_markers(pytest_marks)

        yield item

    def collect(self):
        """Load each document in the given input file into a different test

        Yields:
            YamlItem: Essentially an individual pytest 'test object'
        """

        try:
            # Convert to a list so we can catch parser exceptions
            all_tests = list(
                yaml.load_all(self.fspath.open(encoding="utf-8"), Loader=IncludeLoader)
            )
        except yaml.parser.ParserError as e:
            raise_from(exceptions.BadSchemaError, e)

        for test_spec in all_tests:
            if not test_spec:
                logger.warning("Empty document in input file '%s'", self.fspath)
                continue

            try:
                for i in self._generate_items(test_spec):
                    i.initialise_fixture_attrs()
                    yield i
            except (TypeError, KeyError):
                verify_tests(test_spec, with_plugins=False)
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

        self.global_cfg = {}

    def initialise_fixture_attrs(self):
        # pylint: disable=protected-access,attribute-defined-outside-init
        self.funcargs = {}
        fixtureinfo = self.session._fixturemanager.getfixtureinfo(
            self, self.obj, type(self), funcargs=False
        )
        self._fixtureinfo = fixtureinfo
        self.fixturenames = fixtureinfo.names_closure
        self._request = fixtures.FixtureRequest(self)

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
        self.global_cfg = load_global_cfg(self.config)

        self.global_cfg.setdefault("variables", {})

        load_plugins(self.global_cfg)

        # INTERNAL
        # NOTE - now that we can 'mark' tests, we could use pytest.mark.xfail
        # instead. This doesn't differentiate between an error in verification
        # and an error when running the test though.
        xfail = self.spec.get("_xfail", False)

        try:
            verify_tests(self.spec)

            fixture_values = self._load_fixture_values()
            self.global_cfg["variables"].update(fixture_values)

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

    def repr_failure(self, excinfo):  # pylint: disable=no-self-use
        """ called when self.runtest() raises an exception.

        Todo:
            This stuff is copied from pytest at the moment - needs a bit of
            modifying so that it shows the yaml and all the reasons the test
            failed rather than a traceback
        """

        if self.config.getini("tavern-beta-new-traceback") or self.config.getoption(
            "tavern_beta_new_traceback"
        ):
            if issubclass(excinfo.type, exceptions.TavernException):
                return ReprdError(excinfo, self)

        return super(YamlItem, self).repr_failure(excinfo)

    def reportinfo(self):
        return self.fspath, 0, "{s.path}::{s.name:s}".format(s=self)


class ReprdError(object):
    def __init__(self, exce, item):
        self.exce = exce
        self.item = item

    def _get_available_format_keys(self):
        """Try to get the format variables for the stage

        If we can't get the variable for this specific stage, just return the
        global config which will at least have some format variables

        Returns:
            dict: variables for formatting test
        """
        try:
            # pylint: disable=protected-access
            keys = self.exce._excinfo[1].test_block_config["variables"]
        except AttributeError:
            logger.warning("Unable to read stage variables - error output may be wrong")
            keys = self.item.global_cfg

        return keys

    def _print_format_variables(self, tw, code_lines):
        """Print a list of the format variables and their value at this stage

        If the format variable is not defined, print it in red as '???'

        Args:
            tw (TerminalWriter): Pytest TW instance
            code_lines (list(str)): Source lines for this stage

        Returns:
            list(str): List of all missing format variables
        """

        def read_formatted_vars(lines):
            """Go over all lines and try to find format variables

            This might be a bit wonky if escaped curly braces are used...
            """
            formatted_var_regex = "(?P<format_var>{.*?})"

            for line in lines:
                for match in re.finditer(formatted_var_regex, line):
                    yield match.group("format_var")

        format_variables = list(read_formatted_vars(code_lines))

        keys = self._get_available_format_keys()

        missing = []

        # Print out values of format variables, like Pytest prints out the
        # values of function call variables
        tw.line("Format variables:", white=True, bold=True)
        for var in format_variables:
            if re.match(r"^\s*\{\}\s*", var):
                continue

            try:
                value_at_call = format_keys(var, keys)
            except exceptions.MissingFormatError:
                missing.append(var)
                value_at_call = "???"
                white = False
                red = True
            else:
                white = True
                red = False

            line = "  {} = '{}'".format(var[1:-1], value_at_call)
            tw.line(line, white=white, red=red)  # pragma: no cover

        return missing

    def _print_test_stage(
        self, tw, code_lines, missing_format_vars, line_start
    ):  # pylint: disable=no-self-use
        """Print the direct source lines from this test stage

        If we couldn't get the stage for some reason, print the entire test out.

        If there are any lines which have missing format variables, higlight
        them in red.

        Args:
            tw (Termin): Pytest TW instance
            code_lines (list(str)): Raw source for this stage
            missing_format_vars (list(str)): List of all missing format
                variables for this stage
            line_start (int): Source line of this stage
        """
        if line_start:
            tw.line(
                "Source test stage (line {}):".format(line_start), white=True, bold=True
            )
        else:
            tw.line("Source test stages:", white=True, bold=True)

        for line in code_lines:
            if any(i in line for i in missing_format_vars):
                tw.line(line, red=True)
            else:
                tw.line(line, white=True)

    def _print_formatted_stage(self, tw, stage):  # pylint: disable=no-self-use
        """Print the 'formatted' stage that Tavern will actually use to send the
        request/process the response

        Args:
            tw (TerminalWriter): Pytest TW instance
            stage (dict): The 'final' stage used by Tavern
        """
        tw.line("Formatted stage:", white=True, bold=True)

        # This will definitely exist
        formatted_lines = yaml.dump(stage, default_flow_style=False).split("\n")

        keys = self._get_available_format_keys()

        for line in formatted_lines:
            if not line:
                continue
            if not "{}" in line:
                line = format_keys(line, keys)
            tw.line("  {}".format(line), white=True)

    def _print_errors(self, tw):
        """Print any errors in the 'normal' Pytest style

        Args:
            tw (TerminalWriter): Pytest TW instance
        """
        tw.line("Errors:", white=True, bold=True)

        # Sort of hack, just use this to directly extract the exception format.
        # If this breaks in future, just re-implement it
        e = FormattedExcinfo()
        lines = e.get_exconly(self.exce)
        for line in lines:
            tw.line(line, red=True, bold=True)

    def toterminal(self, tw):
        """Print out a custom error message to the terminal"""

        # Try to get the stage so we can print it out. I'm not sure if the stage
        # will ever NOT be present, but better to check just in case
        try:
            # pylint: disable=protected-access
            stage = self.exce._excinfo[1].stage
        except AttributeError:
            # Fallback, we don't know which stage it is
            spec = self.item.spec
            stages = spec["stages"]

            first_line = stages[0].start_mark.line - 1
            last_line = stages[-1].end_mark.line
            line_start = None
        else:
            first_line = stage.start_mark.line - 1
            last_line = stage.end_mark.line
            line_start = first_line + 1

        def read_relevant_lines(filename):
            """Get lines between start and end mark"""
            with io.open(filename, "r", encoding="utf8") as testfile:
                for idx, line in enumerate(testfile.readlines()):
                    if idx > first_line and idx < last_line:
                        yield line.rstrip()

        code_lines = list(read_relevant_lines(self.item.spec.start_mark.name))

        missing_format_vars = self._print_format_variables(tw, code_lines)
        tw.line("")

        self._print_test_stage(tw, code_lines, missing_format_vars, line_start)
        tw.line("")

        if not missing_format_vars and stage:
            self._print_formatted_stage(tw, stage)
        else:
            tw.line("Unable to get formatted stage", white=True, bold=True)

        tw.line("")

        self._print_errors(tw)

    @property
    def longreprtext(self):
        tw = py.io.TerminalWriter(stringio=True)  # pylint: disable=no-member
        tw.hasmarkup = False
        self.toterminal(tw)
        exc = tw.stringio.getvalue()
        return exc.strip()

    def __str__(self):
        return self.longreprtext
