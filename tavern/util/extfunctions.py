import functools
import importlib
import logging

from . import exceptions


def _getlogger():
    """Get logger for this module

    Have to do it like this because the way that pykwalify load extension
    modules means that getting the logger the normal way just result sin it
    trying to get the root logger which won't log correctly
    """
    return logging.getLogger("tavern.util.extfunctions")


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
    args = ext.get("extra_args") or ()
    kwargs = ext.get("extra_kwargs") or {}
    try:
        func = import_ext_function(ext["function"])
    except KeyError:
        raise exceptions.BadSchemaError(
            "No function specified in external function block"
        )

    @functools.wraps(func)
    def inner(response):
        result = func(response, *args, **kwargs)
        _getlogger().info("Result of calling '%s': '%s'", func, result)
        return result

    inner.func = func

    return inner


def get_wrapped_create_function(ext):
    """Same as get_wrapped_response_function, but don't require a response"""
    args = ext.get("extra_args") or ()
    kwargs = ext.get("extra_kwargs") or {}
    func = import_ext_function(ext["function"])

    @functools.wraps(func)
    def inner():
        result = func(*args, **kwargs)
        _getlogger().info("Result of calling '%s': '%s'", func, result)
        return result

    inner.func = func

    return inner
