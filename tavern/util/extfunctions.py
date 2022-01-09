import functools
import importlib
import logging

from . import exceptions
from .dict_util import deep_dict_merge


def is_ext_function(block):
    """
    Whether the given object is an ext function block

    Args:
        block (object): Any object

    Returns:
        bool: If it is an ext function style dict
    """
    return isinstance(block, dict) and block.get("$ext", None) is not None


def get_pykwalify_logger(module):
    """Get logger for this module

    Have to do it like this because the way that pykwalify load extension
    modules means that getting the logger the normal way just result sin it
    trying to get the root logger which won't log correctly

    Args:
        module (string): name of module to get logger for

    """
    return logging.getLogger(module)


def _getlogger():
    return get_pykwalify_logger("tavern.util.extfunctions")


def import_ext_function(entrypoint):
    """Given a function name in the form of a setuptools entry point, try to
    dynamically load and return it

    Args:
        entrypoint (str): setuptools-style entrypoint in the form
            module.submodule:function

    Returns:
        function: function loaded from entrypoint

    Raises:
        InvalidExtFunctionError: If the module or function did not exist
    """
    logger = _getlogger()

    try:
        module, funcname = entrypoint.split(":")
    except ValueError as e:
        msg = "Expected entrypoint in the form module.submodule:function"
        logger.exception(msg)
        raise exceptions.InvalidExtFunctionError(msg) from e

    try:
        module = importlib.import_module(module)
    except ImportError as e:
        msg = "Error importing module {}".format(module)
        logger.exception(msg)
        raise exceptions.InvalidExtFunctionError(msg) from e

    try:
        function = getattr(module, funcname)
    except AttributeError as e:
        msg = "No function named {} in {}".format(funcname, module)
        logger.exception(msg)
        raise exceptions.InvalidExtFunctionError(msg) from e

    return function


def get_wrapped_response_function(ext):
    """Wraps a ext function with arguments given in the test file

    This is similar to functools.wrap, but this makes sure that 'response' is
    always the first argument passed to the function

    Args:
        ext (dict): $ext function dict with function, extra_args, and
            extra_kwargs to pass

    Returns:
        function: Wrapped function
    """

    func, args, kwargs = _get_ext_values(ext)

    @functools.wraps(func)
    def inner(response):
        result = func(response, *args, **kwargs)
        _getlogger().debug("Result of calling '%s': '%s'", func, result)
        return result

    inner.func = func

    return inner


def get_wrapped_create_function(ext):
    """Same as get_wrapped_response_function, but don't require a response"""

    func, args, kwargs = _get_ext_values(ext)

    @functools.wraps(func)
    def inner():
        result = func(*args, **kwargs)
        _getlogger().debug("Result of calling '%s': '%s'", func, result)
        return result

    inner.func = func

    return inner


def _get_ext_values(ext):
    args = ext.get("extra_args") or ()
    kwargs = ext.get("extra_kwargs") or {}
    try:
        func = import_ext_function(ext["function"])
    except KeyError as e:
        raise exceptions.BadSchemaError(
            "No function specified in external function block"
        ) from e

    return func, args, kwargs


def update_from_ext(request_args, keys_to_check, test_block_config):
    """
    Updates the request_args dict with any values from external functions

    Args:
        request_args (dict): dictionary of request args
        keys_to_check (list): list of keys in request to possibly update from
        test_block_config (dict): whether to merge or replace values
    """

    merge_ext_values = test_block_config.get("merge_ext_values")

    new_args = {}

    for key in keys_to_check:
        try:
            func = get_wrapped_create_function(request_args[key].pop("$ext"))
        except (KeyError, TypeError, AttributeError):
            pass
        else:
            new_args[key] = func()

    _getlogger().debug("Will merge ext values? %s", merge_ext_values)

    if merge_ext_values:
        merged_args = deep_dict_merge(request_args, new_args)
    else:
        merged_args = dict(request_args, **new_args)

    request_args.update(**merged_args)
