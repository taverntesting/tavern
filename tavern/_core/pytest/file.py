import copy
import functools
import itertools
import logging
import typing
from collections.abc import Callable, Iterable, Iterator, Mapping
from typing import Any, Union

import pytest
import yaml
from box import Box
from pytest import Mark

from tavern._core import exceptions
from tavern._core.dict_util import deep_dict_merge, format_keys, get_tavern_box
from tavern._core.extfunctions import get_wrapped_create_function, is_ext_function
from tavern._core.loader import IncludeLoader
from tavern._core.schema.files import verify_tests

from .item import YamlItem
from .util import load_global_cfg

logger: logging.Logger = logging.getLogger(__name__)

T = typing.TypeVar("T")

_format_without_inner: Callable[[T, Mapping], T] = functools.partial(  # type:ignore
    format_keys, no_double_format=False
)


def _format_test_marks(
    original_marks: Iterable[Union[str, dict]], fmt_vars: Mapping, test_name: str
) -> tuple[list[Mark], list[Mapping]]:
    """Given the 'raw' marks from the test and any available format variables,
    generate new  marks for this test

    Args:
        original_marks: Raw string from test - should correspond to either a
            pytest builtin mark or a custom user mark
        fmt_vars: dictionary containing available format variables
        test_name: Name of test (for error logging)

    Returns:
        first element is normal pytest mark objects, second element is all
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

    pytest_marks: list[Mark] = []
    formatted_marks: list[Mapping] = []

    for m in original_marks:
        if isinstance(m, str):
            # a normal mark
            m = _format_without_inner(m, fmt_vars)
            pytest_marks.append(getattr(pytest.mark, m))
        elif isinstance(m, dict):
            # skipif or parametrize (for now)
            for markname, extra_arg in m.items():
                # NOTE
                # cannot do 'skipif' and rely on a parametrized
                # argument.
                try:
                    extra_arg = _format_without_inner(extra_arg, fmt_vars)
                except exceptions.MissingFormatError as e:
                    msg = f"Tried to use mark '{markname}' (with value '{extra_arg}') in test '{test_name}' but one or more format variables was not in any configuration file used by the test"
                    # NOTE
                    # we could continue and let it fail in the test, but
                    # this gives a better indication of what actually
                    # happened (even if it is difficult to test)
                    raise exceptions.MissingFormatError(msg) from e
                else:
                    pytest_marks.append(getattr(pytest.mark, markname)(extra_arg))
                    formatted_marks.append({markname: extra_arg})
        else:
            raise exceptions.BadSchemaError(f"Unexpected mark type '{type(m)}'")

    return pytest_marks, formatted_marks


def _maybe_load_ext(pair):
    """Try to load ext values"""
    key, value = pair

    if is_ext_function(value):
        # If it is an ext function, load the new (or supplemental) value[s]
        ext = value.pop("$ext")
        f = get_wrapped_create_function(ext)
        new_value = f()

        if len(value) == 0:
            # Use only this new value
            return key, new_value
        elif isinstance(new_value, dict):
            # Merge with some existing data. At this point 'value' is known to be a dict.
            return key, deep_dict_merge(value, f())
        else:
            # For example, if it's defined like
            #
            # - testkey: testval
            #   $ext:
            #     function: mod:func
            #
            # and 'mod:func' returns a string, it's impossible to 'merge' with the existing data.
            logger.error("Values still in 'val': %s", value)
            raise exceptions.BadSchemaError(
                f"There were extra key/value pairs in the 'val' for this parametrize mark, but the ext function {ext} returned '{new_value}' (of type {type(new_value)}) that was not a dictionary. It is impossible to merge these values."
            )

    return key, value


def _generate_parametrized_test_items(
    keys: Iterable[Union[str, list, tuple]], vals_combination: Iterable[tuple[str, str]]
) -> tuple[Mapping[str, Any], str]:
    """Generate test name from given key(s)/value(s) combination

    Args:
        keys: list of keys to format name with
        vals_combination this combination of values for the key

    Returns:
        tuple of the variables for the stage and the generated stage name
    """
    flattened_values: list[Iterable[str]] = []
    variables: dict[str, Any] = {}

    # combination of keys and the values they correspond to
    for pair in zip(keys, vals_combination):
        key, value = pair
        # NOTE: If test is invalid, test names generated here will be
        # very weird looking
        if isinstance(key, str):
            variables[key] = value
            flattened_values.append(value)
        else:
            if not isinstance(value, list | tuple):
                value = [value]

            if len(value) != len(key):
                raise exceptions.BadSchemaError(
                    f"Invalid match between numbers of keys and number of values in parametrize mark ({key} keys, {value} values)"
                )

            for subkey, subvalue in zip(key, value):
                variables[subkey] = subvalue
                flattened_values.append(subvalue)

    variables = dict(map(_maybe_load_ext, variables.items()))

    logger.debug("Variables for this combination: %s", variables)
    logger.debug("Values for this combination: %s", flattened_values)

    # Use for formatting parametrized values - eg {}-{}, {}-{}-{}, etc.
    inner_fmt = "-".join(["{}"] * len(flattened_values))
    inner_formatted = inner_fmt.format(*flattened_values)

    return variables, inner_formatted


def _get_parametrized_items(
    parent: pytest.File,
    test_spec: dict,
    parametrize_marks: list[dict],
    pytest_marks: list[pytest.Mark],
) -> Iterator[YamlItem]:
    """Return new items with new format values available based on the mark

    This will change the name from something like 'test a thing' to 'test a
    thing[param1]', 'test a thing[param2]', etc. This probably messes with
    -k

    Note:
        This still has the pytest.mark.parametrize mark on it, though it
        doesn't appear to do anything. This could be removed?
    """

    logger.debug("parametrize marks: %s", parametrize_marks)

    # These should be in the same order as specified in the input file
    vals = [i["parametrize"]["vals"] for i in parametrize_marks]

    logger.debug("(possibly wrapped) values: %s", vals)

    def unwrap_map(value):
        if is_ext_function(value):
            ext = value.pop("$ext")
            f = get_wrapped_create_function(ext)
            new_value = f()
            return new_value

        return value

    vals = list(map(unwrap_map, vals))

    try:
        combined = itertools.product(*vals)
    except TypeError as e:
        raise exceptions.BadSchemaError(
            "Invalid match between numbers of keys and number of values in parametrize mark"
        ) from e

    keys: list[str] = [i["parametrize"]["key"] for i in parametrize_marks]

    for vals_combination in combined:
        logger.debug("Generating test for %s/%s", keys, vals_combination)

        if len(vals_combination) != len(keys):
            raise exceptions.BadSchemaError(
                "Invalid match between numbers of keys and number of values in parametrize mark"
            )

        variables, inner_formatted = _generate_parametrized_test_items(
            keys, vals_combination
        )

        # Change the name
        spec_new = copy.deepcopy(test_spec)
        spec_new["test_name"] = test_spec["test_name"] + f"[{inner_formatted}]"

        logger.debug("New test name: %s", spec_new["test_name"])

        # Make this new thing available for formatting
        spec_new.setdefault("includes", []).append(
            {
                "name": f"parametrized[{inner_formatted}]",
                "description": "autogenerated by Tavern",
                "variables": variables,
            }
        )
        # And create the new item
        item_new = YamlItem.yamlitem_from_parent(
            spec_new["test_name"], parent, spec_new, parent.path
        )
        item_new.add_markers(pytest_marks)

        yield item_new


class YamlFile(pytest.File):
    """Custom `File` class that loads each test block as a different test"""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)

        # This (and the FakeObj below) are to make pytest-pspec not error out.
        # The 'docstring' for this is the filename, the 'docstring' for each
        # individual test is the actual test name.
        class FakeObj:
            __doc__ = str(self.path)

        self.obj = FakeObj

    def _get_test_fmt_vars(self, test_spec: Mapping) -> dict:
        """Get any format variables that can be inferred for the test at this point

        Args:
            test_spec: Test specification, possibly with included config files

        Returns:
            available format variables
        """
        # Get included variables so we can do things like:
        # skipif: {my_integer} > 2
        # skipif: 'https' in '{hostname}'
        # skipif: '{hostname}'.contains('ignoreme')
        fmt_vars: dict = {}

        global_cfg = load_global_cfg(self.config)
        fmt_vars.update(**global_cfg.variables)

        included = test_spec.get("includes", [])
        for i in included:
            fmt_vars.update(**i.get("variables", {}))

        if self.session.config.option.collectonly:
            tavern_box = Box(default_box=True)
        else:
            # Needed if something in a config file uses tavern.env_vars
            tavern_box = get_tavern_box()

        try:
            fmt_vars = _format_without_inner(fmt_vars, tavern_box)
        except exceptions.MissingFormatError as e:
            # eg, if we have {tavern.env_vars.DOESNT_EXIST}
            msg = "Tried to use tavern format variable that did not exist"
            raise exceptions.MissingFormatError(msg) from e

        tavern_box.merge_update(**fmt_vars)
        return tavern_box

    def _generate_items(self, test_spec: dict) -> Iterator[YamlItem]:
        """Modify or generate tests based on test spec

        If there are any 'parametrize' marks, this will generate extra tests
        based on the values

        Args:
            test_spec: Test specification

        Yields:
            Tavern YAML test
        """
        item = YamlItem.yamlitem_from_parent(
            test_spec["test_name"], self, test_spec, self.path
        )

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
                yield from _get_parametrized_items(
                    self, test_spec, parametrize_marks, pytest_marks
                )

                # Only yield the parametrized ones
                return
            else:
                item.add_markers(pytest_marks)

        yield item

    def collect(self) -> Iterator[YamlItem]:
        """Load each document in the given input file into a different test

        Yields:
            Pytest 'test objects'
        """

        try:
            # Convert to a list so we can catch parser exceptions
            all_tests: Iterable[dict] = list(
                yaml.load_all(
                    self.path.open(encoding="utf-8"),
                    Loader=IncludeLoader,  # type:ignore
                )
            )
        except yaml.parser.ParserError as e:
            raise exceptions.BadSchemaError from e

        for test_spec in all_tests:
            if not test_spec:
                logger.warning("Empty document in input file '%s'", self.path)
                continue

            try:
                for i in self._generate_items(test_spec):
                    i.initialise_fixture_attrs()
                    yield i
            except (TypeError, KeyError) as e:
                try:
                    verify_tests(test_spec, with_plugins=False)
                except Exception as e2:
                    raise e2 from e
                else:
                    raise
