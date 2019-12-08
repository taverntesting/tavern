import collections
import logging
import re
import string

from box import Box
import jmespath

from tavern.util.loader import (
    ANYTHING,
    ForceIncludeToken,
    RegexSentinel,
    TypeConvertToken,
    TypeSentinel,
)

from . import exceptions

logger = logging.getLogger(__name__)


class _FormattedString(str):
    """Wrapper class for things that have already been formatted

    This is only used below and should not be used outside this module
    """

    def __init(self, s):
        super(_FormattedString, self).__init__(s)


def _check_and_format_values(to_format, box_vars):
    formatter = string.Formatter()
    would_format = formatter.parse(to_format)

    for (_, field_name, _, _) in would_format:
        if field_name is None:
            continue

        try:
            would_replace = formatter.get_field(field_name, [], box_vars)[0]
        except KeyError as e:
            logger.error(
                "Failed to resolve string [%s] with variables [%s]", to_format, box_vars
            )
            logger.error("Key(s) not found in format: %s", field_name)
            raise exceptions.MissingFormatError(field_name) from e
        except IndexError as e:
            logger.error("Empty format values are invalid")
            raise exceptions.MissingFormatError(field_name) from e
        else:
            if not isinstance(would_replace, (str, int, float)):
                logger.warning(
                    "Formatting '%s' will result in it being coerced to a string (it is a %s)",
                    field_name,
                    type(would_replace),
                )

    return to_format.format(**box_vars)


def _attempt_find_include(to_format, box_vars):
    formatter = string.Formatter()
    would_format = list(formatter.parse(to_format))

    yaml_tag = ForceIncludeToken.yaml_tag

    if len(would_format) != 1:
        raise exceptions.InvalidFormattedJsonError(
            "When using {}, there can only be one exactly format value, but got {}".format(
                yaml_tag, len(would_format)
            )
        )

    (_, field_name, format_spec, conversion) = would_format[0]

    if field_name is None:
        raise exceptions.InvalidFormattedJsonError(
            "Invalid string used for {}".format(yaml_tag)
        )

    pattern = r"{" + field_name + r".*}"

    if not re.match(pattern, to_format):
        raise exceptions.InvalidFormattedJsonError(
            "Invalid format specifier '{}' for {}".format(to_format, yaml_tag)
        )

    if format_spec:
        logger.warning(
            "Conversion specifier '%s' will be ignored for %s", format_spec, to_format
        )

    would_replace = formatter.get_field(field_name, [], box_vars)[0]

    return formatter.convert_field(would_replace, conversion)


def format_keys(val, variables, no_double_format=True):
    """recursively format a dictionary with the given values

    Args:
        val (object): Input dictionary to format
        variables (dict): Dictionary of keys to format it with
        no_double_format (bool): Whether to use the 'inner formatted string' class to avoid double formatting
            This is required if passing something via pytest-xdist, such as markers:
            https://github.com/taverntesting/tavern/issues/431

    Returns:
        dict: recursively formatted dictionary
    """
    formatted = val
    box_vars = Box(variables)

    if isinstance(val, dict):
        formatted = {}
        # formatted = {key: format_keys(val[key], box_vars) for key in val}
        for key in val:
            formatted[key] = format_keys(val[key], box_vars)
    elif isinstance(val, (list, tuple)):
        formatted = [format_keys(item, box_vars) for item in val]
    elif isinstance(formatted, _FormattedString):
        logger.debug("Already formatted %s, not double-formatting", formatted)
    elif isinstance(val, str):
        formatted = _check_and_format_values(val, box_vars)

        if no_double_format:
            formatted = _FormattedString(formatted)
    elif isinstance(val, TypeConvertToken):
        if isinstance(val, ForceIncludeToken):
            formatted = _attempt_find_include(val.value, box_vars)
        else:
            value = format_keys(val.value, box_vars)
            formatted = val.constructor(value)
    else:
        logger.debug("Not formatting something of type '%s'", type(formatted))

    return formatted


def recurse_access_key(data, query):
    """
    Search for something in the given data using the given query.

    Example:

        >>> recurse_access_key({'a': 'b'}, 'a')
        'b'
        >>> recurse_access_key({'a': {'b': ['c', 'd']}}, 'a.b[0]')
        'c'

    Args:
        data (dict, list): Data to search in
        query (str): Query to run

    Returns:
        object: Whatever was found by the search
    """

    try:
        from_jmespath = jmespath.search(query, data)
    except jmespath.exceptions.ParseError as e:
        logger.error("Error parsing JMES query")

        try:
            _deprecated_recurse_access_key(data, query.split("."))
        except (IndexError, KeyError):
            logger.debug("Nothing found searching using old method")
        else:
            # If we found a key using 'old' style searching
            logger.warning(
                "Something was found using 'old style' searching in the response - please change the query to use jmespath instead - see http://jmespath.org/ for more information"
            )

        raise exceptions.JMESError("Invalid JMES query") from e

    return from_jmespath


def _deprecated_recurse_access_key(current_val, keys):
    """ Given a list of keys and a dictionary, recursively access the dicionary
    using the keys until we find the key its looking for

    If a key is an integer, it will convert it and use it as a list index

    Example:

        >>> _deprecated_recurse_access_key({'a': 'b'}, ['a'])
        'b'
        >>> _deprecated_recurse_access_key({'a': {'b': ['c', 'd']}}, ['a', 'b', '0'])
        'c'

    Args:
        current_val (dict): current dictionary we have recursed into
        keys (list): list of str/int of subkeys

    Raises:
        IndexError: list index not found in data
        KeyError: dict key not found in data

    Returns:
        str or dict: value of subkey in dict
    """
    logger.debug("Recursively searching for '%s' in '%s'", keys, current_val)

    if not keys:
        return current_val
    else:
        current_key = keys.pop(0)

        try:
            current_key = int(current_key)
        except ValueError:
            pass

        try:
            return _deprecated_recurse_access_key(current_val[current_key], keys)
        except (IndexError, KeyError, TypeError) as e:
            logger.error(
                "%s accessing data - looking for '%s' in '%s'",
                type(e).__name__,
                current_key,
                current_val,
            )
            raise


def deep_dict_merge(initial_dct, merge_dct):
    """ Recursive dict merge. Instead of updating only top-level keys,
    dict_merge recurses down into dicts nested to an arbitrary depth
    and returns the merged dict. Keys values present in merge_dct take
    precedence over values in initial_dct.
    Modified from: https://gist.github.com/angstwad/bf22d1822c38a92ec0a9

    Params:
        initial_dct: dict onto which the merge is executed
        merge_dct: dct merged into dct

    Returns:
        dict: recursively merged dict
    """
    dct = initial_dct.copy()

    for k in merge_dct:
        if (
            k in dct
            and isinstance(dct[k], dict)
            and isinstance(merge_dct[k], collections.Mapping)
        ):
            dct[k] = deep_dict_merge(dct[k], merge_dct[k])
        else:
            dct[k] = merge_dct[k]

    return dct


def check_expected_keys(expected, actual):
    """Check that a set of expected keys is a superset of the actual keys

    Args:
        expected (list, set, dict): keys we expect
        actual (list, set, dict): keys we have got from the input

    Raises:
        UnexpectedKeysError: If not actual <= expected
    """
    expected = set(expected)
    keyset = set(actual)

    if not keyset <= expected:
        unexpected = keyset - expected

        logger.debug("Valid keys = %s, actual keys = %s", expected, keyset)

        msg = "Unexpected keys {}".format(unexpected)
        logger.error(msg)
        raise exceptions.UnexpectedKeysError(msg)


def yield_keyvals(block):
    """Return indexes, keys and expected values for matching recursive keys

    Given a list or dict, return a 3-tuple of the 'split' key (key split on
    dots), the original key, and the expected value. If the input is a list, it
    is enumerated so the 'keys' are just [0, 1, 2, ...]

    Example:

        Matching a dictionary with a couple of keys:

        >>> gen = yield_keyvals({"a": {"b": "c"}})
        >>> next(gen)
        (['a'], 'a', {'b': 'c'})

        Matching nested key access:

        >>> gen = yield_keyvals({"a.b.c": "d"})
        >>> next(gen)
        (['a', 'b', 'c'], 'a.b.c', 'd')

        Matching a list of items:

        >>> gen = yield_keyvals(["a", "b", "c"])
        >>> next(gen)
        (['0'], '0', 'a')
        >>> next(gen)
        (['1'], '1', 'b')
        >>> next(gen)
        (['2'], '2', 'c')

    Args:
        block (dict, list): input matches

    Yields:
        (list, str, str): key split on dots, key, expected value
    """
    if isinstance(block, dict):
        for joined_key, expected_val in block.items():
            split_key = joined_key.split(".")
            yield split_key, joined_key, expected_val
    else:
        for idx, val in enumerate(block):
            sidx = str(idx)
            yield [sidx], sidx, val


def check_keys_match_recursive(expected_val, actual_val, keys, strict=True):
    """Utility to recursively check response values

    expected and actual both have to be of the same type or it will raise an
    error.

    Example:

        >>> check_keys_match_recursive({"a": {"b": "c"}}, {"a": {"b": "c"}}, []) is None
        True
        >>> check_keys_match_recursive({"a": {"b": "c"}}, {"a": {"b": "d"}}, []) # doctest: +IGNORE_EXCEPTION_DETAIL
        Traceback (most recent call last):
          File "/home/michael/code/tavern/tavern/tavern/util/dict_util.py", line 223, in check_keys_match_recursive
        tavern.util.exceptions.KeyMismatchError: Key mismatch: (expected["a"]["b"] = 'c', actual["a"]["b"] = 'd')

    Todo:
        This could be turned into a single-dispatch function for cleaner
        code and to remove a load of the isinstance checks

    Args:
        expected_val (dict, list, str): expected value
        actual_val (dict, list, str): actual value
        keys (list): any keys which have been recursively parsed to get to this
            point. Used for debug output.
        strict (bool): Whether 'strict' key checking should be done. If this is
            False, a mismatch in dictionary keys between the expected and the
            actual values will not raise an error (but a mismatch in value will
            raise an error)

    Raises:
        KeyMismatchError: expected_val and actual_val did not match
    """

    # pylint: disable=too-many-locals

    def full_err():
        """Get error in the format:

        a["b"]["c"] = 4, b["b"]["c"] = {'key': 'value'}
        """

        def _format_err(which):
            return "{}{}".format(which, "".join('["{}"]'.format(key) for key in keys))

        e_formatted = _format_err("expected")
        a_formatted = _format_err("actual")
        return "{} = '{}' (type = {}), {} = '{}' (type = {})".format(
            e_formatted,
            expected_val,
            type(expected_val),
            a_formatted,
            actual_val,
            type(actual_val),
        )

    actual_type = type(actual_val)

    if expected_val is ANYTHING:
        # Match anything. We could just early exit here but having the debug
        # logging below is useful
        expected_matches = True
    elif isinstance(expected_val, TypeSentinel):
        # If the 'expected' type is actually just a sentinel for another type,
        # then it should match
        expected_matches = expected_val.constructor == actual_type
    else:
        # Normal matching
        expected_matches = (
            # If they are the same type
            isinstance(expected_val, actual_type)
            or
            # Handles the case where, for example, the 'actual type' returned by
            # a custom backend returns an OrderedDict, which is a subclass of
            # dict but will raise a confusing error if the contents are
            # different
            issubclass(actual_type, type(expected_val))
        )

    try:
        assert actual_val == expected_val
    except AssertionError as e:
        # At this point, there is likely to be an error unless we're using any
        # of the type sentinels

        if not (expected_val is ANYTHING):  # pylint: disable=superfluous-parens
            if not expected_matches:
                if isinstance(expected_val, RegexSentinel):
                    msg = "Expected a string to match regex '{}' ({})".format(
                        expected_val.compiled, full_err()
                    )
                else:
                    msg = "Type of returned data was different than expected ({})".format(
                        full_err()
                    )

                raise exceptions.KeyMismatchError(msg) from e

        if isinstance(expected_val, dict):
            akeys = set(actual_val.keys())
            ekeys = set(expected_val.keys())

            if akeys != ekeys:
                extra_actual_keys = akeys - ekeys
                extra_expected_keys = ekeys - akeys

                msg = ""
                if extra_actual_keys:
                    msg += " - Extra keys in response: {}".format(extra_actual_keys)
                if extra_expected_keys:
                    msg += " - Keys missing from response: {}".format(
                        extra_expected_keys
                    )

                full_msg = "Structure of returned data was different than expected {} ({})".format(
                    msg, full_err()
                )

                # If there are more keys in 'expected' compared to 'actual',
                # this is still a hard error and we shouldn't continue
                if extra_expected_keys or strict:
                    raise exceptions.KeyMismatchError(full_msg) from e
                else:
                    logger.debug(
                        "Mismatch in returned data, continuing due to strict=%s: %s",
                        strict,
                        full_msg,
                        exc_info=True,
                    )

            # If strict is True, an error will be raised above. If not, recurse
            # through both sets of keys and just ignore missing ones
            to_recurse = akeys | ekeys

            for key in to_recurse:
                try:
                    check_keys_match_recursive(
                        expected_val[key], actual_val[key], keys + [key], strict
                    )
                except KeyError:
                    logger.debug(
                        "Skipping comparing missing key '%s' due to strict=%s",
                        key,
                        strict,
                    )
        elif isinstance(expected_val, list):
            if not strict:
                missing = []

                actual_iter = iter(actual_val)

                # Iterate over list items to see if any of them match _IN ORDER_
                for i, e_val in enumerate(expected_val):
                    while 1:
                        try:
                            current_response_val = next(actual_iter)
                        except StopIteration:
                            # Still iterating checking for a value, but ran out of response values
                            logger.debug("Ran out of list response items to check")
                            missing.append(e_val)
                            break
                        else:
                            logger.debug(
                                "Got '%s' from response to check against '%s' from expected",
                                current_response_val,
                                e_val,
                            )

                        # Found one - check if it matches
                        try:
                            check_keys_match_recursive(
                                e_val, current_response_val, keys + [i], strict
                            )
                        except exceptions.KeyMismatchError:
                            # Doesn't match what we're looking for
                            logger.debug(
                                "%s did not match next response value %s",
                                e_val,
                                current_response_val,
                            )
                        else:
                            logger.debug("'%s' present in response", e_val)
                            break

                if missing:
                    msg = "List item(s) not present in response: {}".format(missing)
                    raise exceptions.KeyMismatchError(msg) from e

                logger.debug("All expected list items present")
            else:
                if len(expected_val) != len(actual_val):
                    raise exceptions.KeyMismatchError(
                        "Length of returned list was different than expected - expected {} items from got {} ({}".format(
                            len(expected_val), len(actual_val), full_err()
                        )
                    ) from e

                for i, (e_val, a_val) in enumerate(zip(expected_val, actual_val)):
                    try:
                        check_keys_match_recursive(e_val, a_val, keys + [i], strict)
                    except exceptions.KeyMismatchError as sub_e:
                        # This should _ALWAYS_ raise an error, but it will be more
                        # obvious where the error came from (in python 3 at least)
                        # and will take ANYTHING into account
                        raise sub_e from e
        elif expected_val is ANYTHING:
            logger.debug("Actual value = '%s' - matches !anything", actual_val)
        elif isinstance(expected_val, TypeSentinel) and expected_matches:
            if isinstance(expected_val, RegexSentinel):
                if not expected_val.passes(actual_val):
                    raise exceptions.KeyMismatchError(
                        "Regex mismatch: ({})".format(full_err())
                    ) from e

            logger.debug(
                "Actual value = '%s' - matches !any%s",
                actual_val,
                expected_val.constructor,
            )
        else:
            raise exceptions.KeyMismatchError(
                "Key mismatch: ({})".format(full_err())
            ) from e
