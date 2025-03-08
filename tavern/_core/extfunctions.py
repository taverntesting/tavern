import functools
import importlib
import logging
from collections.abc import Callable, Iterable, Mapping
from typing import Any, Optional

from tavern._core import exceptions

from .dict_util import deep_dict_merge


def is_ext_function(block: Any) -> bool:
    """
    Whether the given object is an ext function block

    Args:
        block: Any object

    Returns:
        If it is an ext function style dict
    """
    return isinstance(block, dict) and block.get("$ext", None) is not None


def get_pykwalify_logger(module: Optional[str]) -> logging.Logger:
    """Get logger for this module

    Have to do it like this because the way that pykwalify load extension
    modules means that getting the logger the normal way just result sin it
    trying to get the root logger which won't log correctly

    Args:
        module: name of module to get logger for

    Returns:
        logger for given module
    """
    return logging.getLogger(module)


def _getlogger() -> logging.Logger:
    """Get logger for this module"""
    return get_pykwalify_logger("tavern._core.extfunctions")


def import_ext_function(entrypoint: str) -> Callable:
    """Given a function name in the form of a setuptools entry point, try to
    dynamically load and return it

    Args:
        entrypoint: setuptools-style entrypoint in the form
            module.submodule:function

    Returns:
        function loaded from entrypoint

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
        imported = importlib.import_module(module)
    except ImportError as e:
        msg = f"Error importing module {module}"
        logger.exception(msg)
        raise exceptions.InvalidExtFunctionError(msg) from e

    try:
        function = getattr(imported, funcname)
    except AttributeError as e:
        msg = f"No function named {funcname} in {module}"
        logger.exception(msg)
        raise exceptions.InvalidExtFunctionError(msg) from e

    return function


def get_wrapped_response_function(ext: Mapping) -> Callable:
    """Wraps a ext function with arguments given in the test file

    This is similar to functools.wrap, but this makes sure that 'response' is
    always the first argument passed to the function

    Args:
        ext: $ext function dict with function, extra_args, and
            extra_kwargs to pass

    Returns:
        Wrapped function
    """

    func, args, kwargs = _get_ext_values(ext)

    @functools.wraps(func)
    def inner(response):
        result = func(response, *args, **kwargs)
        _getlogger().debug("Result of calling '%s': '%s'", func, result)
        return result

    inner.func = func  # type: ignore

    return inner


def get_wrapped_create_function(ext: Mapping) -> Callable:
    """Same as get_wrapped_response_function, but don't require a response"""

    func, args, kwargs = _get_ext_values(ext)

    @functools.wraps(func)
    def inner():
        result = func(*args, **kwargs)
        _getlogger().debug("Result of calling '%s': '%s'", func, result)
        return result

    inner.func = func  # type: ignore

    return inner


def _get_ext_values(ext: Mapping) -> tuple[Callable, Iterable, Mapping]:
    if not isinstance(ext, Mapping):
        raise exceptions.InvalidExtFunctionError(
            f"ext block should be a dict, but it was a {type(ext)}"
        )

    args = ext.get("extra_args") or ()
    kwargs = ext.get("extra_kwargs") or {}
    try:
        func = import_ext_function(ext["function"])
    except KeyError as e:
        raise exceptions.BadSchemaError(
            "No function specified in external function block"
        ) from e

    return func, args, kwargs


def update_from_ext(request_args: dict, keys_to_check: list[str]) -> None:
    """
    Updates the request_args dict with any values from external functions

    Args:
        request_args: dictionary of request args
        keys_to_check: list of keys in request to possibly update from
    """

    new_args = {}
    logger = _getlogger()

    for key in keys_to_check:
        try:
            block = request_args[key]
        except KeyError:
            logger.debug("No %s block", key)
            continue

        try:
            pop = block.pop("$ext")
        except (KeyError, AttributeError, TypeError):
            logger.debug("No ext functions in %s block", key)
            continue

        func = get_wrapped_create_function(pop)
        new_args[key] = func()

    merged_args = deep_dict_merge(request_args, new_args)

    request_args.update(**merged_args)
