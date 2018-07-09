import collections
import warnings
import logging
from builtins import str as ustr

from future.utils import raise_from
from box import Box

from tavern.util.loader import TypeConvertToken, ANYTHING, TypeSentinel
from . import exceptions


logger = logging.getLogger(__name__)


def format_keys(val, variables):
    """recursively format a dictionary with the given values

    Args:
        val (dict): Input dictionary to format
        variables (dict): Dictionary of keys to format it with

    Returns:
        dict: recursively formatted dictionary
    """
    formatted = val
    box_vars = Box(variables)

    if isinstance(val, dict):
        formatted = {}
        #formatted = {key: format_keys(val[key], box_vars) for key in val}
        for key in val:
            formatted[key] = format_keys(val[key], box_vars)
    elif isinstance(val, (list, tuple)):
        formatted = [format_keys(item, box_vars) for item in val]
    elif isinstance(val, (ustr, str)):
        try:
            formatted = val.format(**box_vars)
        except KeyError as e:
            logger.error("Failed to resolve string [%s] with variables [%s]",
                         val, box_vars)
            logger.error("Key(s) not found in format: %s", e.args)
            raise_from(exceptions.MissingFormatError(e.args), e)
        except IndexError as e:
            logger.error("Empty format values are invalid")
            raise_from(exceptions.MissingFormatError(e.args), e)
    elif isinstance(val, TypeConvertToken):
        value = format_keys(val.value, box_vars)
        formatted = val.constructor(value)

    return formatted


def recurse_access_key(current_val, keys):
    """ Given a list of keys and a dictionary, recursively access the dicionary
    using the keys until we find the key its looking for

    If a key is an integer, it will convert it and use it as a list index

    Example:

        >>> recurse_access_key({'a': 'b'}, ['a'])
        'b'
        >>> recurse_access_key({'a': {'b': ['c', 'd']}}, ['a', 'b', '0'])
        'c'

    Args:
        current_val (dict): current dictionary we have recursed into
        keys (list): list of str/int of subkeys

    Returns:
        str or dict: value of subkey in dict
    """
    if not keys:
        return current_val
    else:
        current_key = keys.pop(0)

        try:
            current_key = int(current_key)
        except ValueError:
            pass

        return recurse_access_key(current_val[current_key], keys)


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
        if (k in dct and isinstance(dct[k], dict)
                and isinstance(merge_dct[k], collections.Mapping)):
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

    # pylint: disable=too-many-locals,too-many-statements

    def full_err():
        """Get error in the format:

        a["b"]["c"] = 4, b["b"]["c"] = {'key': 'value'}
        """
        def _format_err(which):
            return "{}{}".format(which, "".join('["{}"]'.format(key) for key in keys))

        e_formatted = _format_err("expected")
        a_formatted = _format_err("actual")
        return "{} = '{}', {} = '{}'".format(e_formatted, expected_val,
            a_formatted, actual_val)

    # Check required because of python 2/3 unicode compatability when loading yaml
    if isinstance(actual_val, ustr):
        actual_type = str
    else:
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

        if not (expected_val is ANYTHING): # pylint: disable=superfluous-parens
            # NOTE
            # Second part of this check will be removed in future - see deprecation
            # warning below for details
            if not expected_matches and expected_val is not None:
                raise_from(exceptions.KeyMismatchError("Type of returned data was different than expected ({})".format(full_err())), e)

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
                    msg += " - Keys missing from response: {}".format(extra_expected_keys)

                full_msg = "Structure of returned data was different than expected {} ({})".format(msg, full_err())

                # If there are more keys in 'expected' compared to 'actual',
                # this is still a hard error and we shouldn't continue
                if extra_expected_keys or strict:
                    raise_from(exceptions.KeyMismatchError(full_msg), e)
                else:
                    logger.warning(full_msg, exc_info=True)

            # If strict is True, an error will be raised above. If not, recurse
            # through both sets of keys and just ignore missing ones
            to_recurse = akeys | ekeys

            for key in to_recurse:
                try:
                    check_keys_match_recursive(expected_val[key], actual_val[key], keys + [key], strict)
                except KeyError:
                    logger.debug("Skipping comparing missing key %s due to strict=%s", key, strict)
        elif isinstance(expected_val, list):
            if len(expected_val) != len(actual_val):
                raise_from(exceptions.KeyMismatchError("Length of returned list was different than expected - expected {} items, got {} ({})".format(len(expected_val), len(actual_val), full_err())), e)

            # TODO
            # Check things in the wrong order?

            for i, (e_val, a_val) in enumerate(zip(expected_val, actual_val)):
                try:
                    check_keys_match_recursive(e_val, a_val, keys + [i], strict)
                except exceptions.KeyMismatchError as sub_e:
                    # This will still raise an error, but it will be more
                    # obvious where the error came from (in python 3 at least)
                    # and will take ANYTHING into account
                    raise_from(sub_e, e)
        elif expected_val is None:
            warnings.warn("Expected value was 'null', so this check will pass - this will be removed in a future version. IF you want to check against 'any' value, use '!anything' instead.", FutureWarning)
        elif expected_val is ANYTHING:
            logger.debug("Actual value = '%s' - matches !anything", actual_val)
        elif isinstance(expected_val, TypeSentinel) and expected_matches:
            logger.debug("Actual value = '%s' - matches !any%s", actual_val, expected_val.constructor)
        else:
            raise_from(exceptions.KeyMismatchError("Key mismatch: ({})".format(full_err())), e)
