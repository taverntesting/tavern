import dataclasses
import logging
from typing import Any, Protocol, runtime_checkable

import starlark

_STARLARK_PRIMITIVES = (str, int, float, bool, type(None))

logger = logging.getLogger(__name__)


@runtime_checkable
class StarlarkConvertible(Protocol):
    """Protocol for objects that know how to convert themselves to Starlark.

    Implemented by anything which requires special handling of values
    """

    def to_starlark(self) -> Any:
        """Convert this object to a Starlark-safe value."""
        raise NotImplementedError


def to_starlark(obj: Any) -> Any:
    """Recursively convert an arbitrary Python object to a Starlark-safe value.

    If it's a StarlarkConvertible then use the specific implementation.

    Primitives, dicts (with string keys) and lists are kept as-is (recursed).
    Everything else is wrapped in an ``OpaquePythonObject`` so it can be passed
    through Starlark without triggering JSON serialisation.
    """
    if isinstance(obj, StarlarkConvertible):
        return obj.to_starlark()
    if isinstance(obj, _STARLARK_PRIMITIVES):
        return obj
    if isinstance(obj, starlark.OpaquePythonObject):
        return obj  # already wrapped
    if dataclasses.is_dataclass(obj):
        return to_starlark(dataclasses.asdict(obj))  # type:ignore
    if isinstance(obj, dict):
        return {k: to_starlark(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [to_starlark(item) for item in obj]
    return starlark.OpaquePythonObject(obj)


def from_starlark(obj: Any) -> Any:
    """Recursively convert a Starlark value back to a plain Python object.

    Primitives, dicts and lists are recursed into; anything else is returned
    as-is. Values wrapped in an ``OpaquePythonObject`` on the way in are already
    unwrapped by the time they arrive back here, so there is nothing to undo.
    """
    if isinstance(obj, _STARLARK_PRIMITIVES):
        return obj
    if isinstance(obj, dict):
        return {k: from_starlark(v) for k, v in obj.items()}
    if isinstance(obj, list | tuple):
        return [from_starlark(item) for item in obj]
    return obj
