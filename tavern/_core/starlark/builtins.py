"""Starlark library functions shared between control_flow scripts and per-stage expressions.

These are the parts of the Starlark environment which do not need to run a stage, so
they can be used from the lightweight per-stage expressions as well as from a full
``control_flow`` script.

This module must not import anything from tavern._core.run, and must not import starlark
at the top level, so that it can be imported (lazily) from the normal non-starlark test
path.
"""

import functools
import importlib.resources
import logging
import re
import time
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import starlark

logger: logging.Logger = logging.getLogger(__name__)


def wrap_callable(fn):
    """Decorator that converts all arguments from starlark→Python before
    calling *fn*, and converts the return value from Python→starlark."""

    from .types import from_starlark, to_starlark

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        converted_args = [from_starlark(a) for a in args]
        converted_kwargs = {k: from_starlark(v) for k, v in kwargs.items()}
        result = fn(*converted_args, **converted_kwargs)
        return to_starlark(result)

    return wrapper


def get_helpers_source() -> str:
    """Load the Starlark builtins from the tavern_helpers.star file.

    Returns:
        The Starlark code for built-in helper functions
    """
    return (
        importlib.resources.files(__package__)
        .joinpath("tavern_helpers.star")
        .read_text()
    )


def _match_dict(result: "re.Match | None") -> dict | None:
    if result is None:
        return None
    return {
        "group0": result.group(0),
        "groups": list(result.groups()),
        "start": result.start(),
        "end": result.end(),
    }


@wrap_callable
def re_match(pattern: str, string: str | bytes) -> dict | None:
    if isinstance(string, bytes):
        string = string.decode("utf-8")
    return _match_dict(re.match(pattern, string))


@wrap_callable
def re_search(pattern: str, string: str | bytes) -> dict | None:
    if isinstance(string, bytes):
        string = string.decode("utf-8")
    return _match_dict(re.search(pattern, string))


@wrap_callable
def re_sub(pattern: str, repl: str, string: str | bytes) -> str:
    if isinstance(string, bytes):
        return re.sub(pattern, repl, string.decode("utf-8"))
    return re.sub(pattern, repl, string)


@wrap_callable
def time_sleep(seconds: float) -> None:
    time.sleep(seconds)


@wrap_callable
def log(s: str) -> None:
    """log a string to stdout."""
    logger.info(s)


def register_library_builtins(module: "starlark.Module") -> None:
    """Add the functions which don't need to run a stage to a module

    Apart from 'log' these are the dunder names which tavern_helpers.star wraps up into
    the 're' and 'time' structs.

    Args:
        module: the starlark module to add them to
    """
    module.add_callable("log", log)
    module.add_callable("__re_match", re_match)
    module.add_callable("__re_search", re_search)
    module.add_callable("__re_sub", re_sub)
    module.add_callable("__time_sleep", time_sleep)
