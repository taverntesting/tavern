import itertools
from builtins import str as ustr

import copy
import logging
import os

import pytest
import yaml
from future.utils import raise_from

from box import Box
from tavern.schemas.files import verify_tests
from tavern.util import exceptions
from tavern.util.dict_util import format_keys
from tavern.util.loader import IncludeLoader

from .item import YamlItem
from .util import load_global_cfg

logger = logging.getLogger(__name__)


def _format_test_marks(original_marks, fmt_vars, test_name):
    """Given the 'raw' marks from the test and any available format variables,
    generate new  marks for this test

    Args:
        original_marks (list): Raw string from test - should correspond to either a
            pytest builtin mark or a custom user mark
        fmt_vars (dict): dictionary containing available format variables
        test_name (str): Name of test (for error logging)

    Returns:
        tuple: first element is normal pytest mark objects, second element is all
            marks which were formatted (no matter their content)

    Todo:
        Fix doctests below - failing due to missing pytest markers

    Example:

        # >>> _format_test_marks([], {}, 'abc')
        # ([], [])
        # >>> _format_test_marks(['tavernmarker'], {}, 'abc')
        # (['tavernmarker'], [])
        # >>> _format_test_marks(['{formatme}'], {'formatme': 'tavernmarker'}, 'abc')
        # (['tavernmarker'], [])
        # >>> _format_test_marks([{'skipif': '{skiptest}'}], {'skiptest': true}, 'abc')
        # (['tavernmarker'], [])

    """

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
                        markname, extra_arg, test_name
                    )
                    # NOTE
                    # we could continue and let it fail in the test, but
                    # this gives a better indication of what actually
                    # happened (even if it is difficult to test)
                    raise_from(exceptions.MissingFormatError(msg), e)
                else:
                    pytest_marks.append(getattr(pytest.mark, markname)(extra_arg))
                    formatted_marks.append({markname: extra_arg})
        else:
            raise exceptions.BadSchemaError("Unexpected mark type '{}'".format(type(m)))

    return pytest_marks, formatted_marks


def _generate_parametrized_test_items(keys, vals_combination):
    """Generate test name from given key(s)/value(s) combination

    Args:
        keys (list): list of keys to format name with
        vals_combination (tuple(str)): this combination of values for the key
    """
    flattened_values = []
    variables = {}

    # combination of keys and the values they correspond to
    for pair in zip(keys, vals_combination):
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
    logger.debug("Values for this combination: %s", flattened_values)

    def u2string(s):
        """
        Takes an int, string, or bytes and gets it in a format suitable
        for formatting

        Args:
            s (object): something to format

        Returns:
            str: correctly formatted string
        """
        if isinstance(s, str):
            return s
        elif isinstance(s, ustr):
            return s.encode("utf8")
        else:
            return s

    flattened_values = list(map(u2string, flattened_values))

    # Use for formatting parametrized values - eg {}-{}, {}-{}-{}, etc.
    inner_fmt = "-".join(["{}"] * len(flattened_values))
    inner_formatted = inner_fmt.format(*flattened_values)

    return variables, inner_formatted


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
            variables, inner_formatted = _generate_parametrized_test_items(
                keys, vals_combination
            )

            # Change the name
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
            pytest_marks, formatted_marks = _format_test_marks(
                original_marks, fmt_vars, test_spec["test_name"]
            )

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
