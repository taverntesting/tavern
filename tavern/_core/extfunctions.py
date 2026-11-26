import functools
import importlib
import logging
from collections.abc import Callable, Iterable, Mapping
from typing import Any

from box import Box, BoxList

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


def get_pykwalify_logger(module: str | None) -> logging.Logger:
    """Get logger for this module

    Have to do it like this because the way that pykwalify load extension
    modules means that getting the logger the normal way just results in it
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


def _resolve_nested_ext(value: Any) -> Any:
    """Call any '$ext' functions found inside part of a request block

    A dict containing '$ext' is handled the same way as the top level of a
    request block: a mapping returned by the function is merged into the
    rest of the dict, and anything else replaces the dict entirely.

    Boxes and tuples are not searched. format_keys rebuilds everything
    written in the test as plain dicts and lists, so a Box here is a value
    that was pulled in from a variable with !force_format_include. That is
    data rather than part of the test, and a '$ext' key in it is left alone.
    A Box does not convert tuples, and YAML cannot produce one, so a tuple
    is treated as included data as well.

    Args:
        value: part of a request block, after formatting

    Returns:
        value with the results of any '$ext' functions applied
    """
    if isinstance(value, (Box, BoxList, tuple)):
        return value

    if isinstance(value, list):
        return [_resolve_nested_ext(item) for item in value]

    if not isinstance(value, dict):
        return value

    result = None

    if "$ext" in value:
        result = get_wrapped_create_function(value["$ext"])()

        if not isinstance(result, Mapping):
            return result

    resolved = {
        key: _resolve_nested_ext(item) for key, item in value.items() if key != "$ext"
    }

    if result is None:
        return resolved

    return deep_dict_merge(resolved, result)


def update_from_ext(request_args: dict, keys_to_check: list[str]) -> None:
    """
    Updates the request_args dict with any values from external functions

    '$ext' can be used at the top level of a block or anywhere inside it. See
    _resolve_nested_ext for how nested blocks are handled.

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
        else:
            func = get_wrapped_create_function(pop)
            new_args[key] = func()

            if not isinstance(new_args[key], Mapping):
                # This replaces the whole block, so there is nothing left in
                # it to look through
                continue

        request_args[key] = _resolve_nested_ext(block)

    merged_args = deep_dict_merge(request_args, new_args)

    request_args.update(**merged_args)
