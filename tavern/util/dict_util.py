import collections

from future.utils import raise_from

from .exceptions import MissingFormatError


def format_keys(val, variables):
    """recursively format a dictionary with the given values

    Args:
        val (dict): Input dictionary to format
        variables (dict): Dictionary of keys to format it with

    Returns:
        dict: recursively formatted dictionary
    """
    formatted = val

    if isinstance(val, dict):
        formatted = {}
        #formatted = {key: format_keys(val[key], variables) for key in val}
        for key in val:
            formatted[key] = format_keys(val[key], variables)
    elif isinstance(val, str):
        try:
            formatted = val.format(**variables)
        except KeyError as e:
            raise_from(MissingFormatError(e.args), e)

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
