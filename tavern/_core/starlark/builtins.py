"""Bindings for the helper 'library' modules loaded from tavern_helpers.star.

These are the parts of the Starlark environment which do not need a pipeline runner -
're', 'time' and 'log'. They are shared between a full 'control_flow' script and the
per-stage expressions, which can also load them but cannot run stages.

This module must not import anything from tavern._core.run, so that it can be imported
from the per-stage expression path.
"""

import functools
import importlib.resources
import logging
import re
import time
from typing import TYPE_CHECKING, Any

from .types import from_starlark, to_starlark

if TYPE_CHECKING:
    import starlark

logger: logging.Logger = logging.getLogger(__name__)


def wrap_callable(fn):
    """Decorator that converts all arguments from starlark→Python before
    calling *fn*, and converts the return value from Python→starlark."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        converted_args = [from_starlark(a) for a in args]
        converted_kwargs = {k: from_starlark(v) for k, v in kwargs.items()}
        result = fn(*converted_args, **converted_kwargs)
        return to_starlark(result)

    return wrapper


def get_starlark_builtins() -> str:
    """Load the Starlark builtins from the tavern_helpers.star file.

    Returns:
        The Starlark code for built-in helper functions
    """
    return (
        importlib.resources.files(__package__)
        .joinpath("tavern_helpers.star")
        .read_text()
    )


def _match_to_dict(result: "re.Match | None") -> dict | None:
    if result is None:
        return None
    return {
        "group0": result.group(0),
        "groups": list(result.groups()),
        "start": result.start(),
        "end": result.end(),
    }


def add_library_callables(module: "starlark.Module") -> None:
    """Add the dunder bindings which the 're', 'time' and 'log' helpers wrap

    Args:
        module: the starlark module to add them to
    """

    @wrap_callable
    def log(s: str) -> None:
        """log a string to stdout."""
        logger.info(s)

    module.add_callable("log", log)

    @wrap_callable
    def re_match(pattern: str, string: str | bytes) -> dict | None:
        if isinstance(string, bytes):
            string = string.decode("utf-8")
        return _match_to_dict(re.match(pattern, string))

    module.add_callable("__re_match", re_match)

    @wrap_callable
    def re_search(pattern: str, string: str | bytes) -> dict | None:
        if isinstance(string, bytes):
            string = string.decode("utf-8")
        return _match_to_dict(re.search(pattern, string))

    module.add_callable("__re_search", re_search)

    @wrap_callable
    def re_sub(pattern: str, repl: str, string: str | bytes) -> str:
        if isinstance(string, bytes):
            return re.sub(pattern, repl, string.decode("utf-8"))
        return re.sub(pattern, repl, string)

    module.add_callable("__re_sub", re_sub)

    @wrap_callable
    def time_sleep(seconds: float) -> None:
        time.sleep(seconds)

    module.add_callable("__time_sleep", time_sleep)


def add_unavailable_run_stage(module: "starlark.Module", reason: str) -> None:
    """Bind a 'run_stage' which just explains why it can't be used

    tavern_helpers.star always defines 'run_stage', so somewhere which can't run stages
    still has to bind something for it to call.

    Args:
        module: the starlark module to add it to
        reason: message explaining why running a stage isn't possible here
    """
    from tavern._core import exceptions

    @wrap_callable
    def run_stage_unavailable(*args: Any, **kwargs: Any) -> Any:
        raise exceptions.StarlarkError(reason)

    module.add_callable("__run_stage", run_stage_unavailable)
