from typing import Any

import starlark

_STARLARK_PRIMITIVES = (str, int, float, bool, type(None))


def to_starlark(obj: Any) -> Any:
    """Recursively convert an arbitrary Python object to a Starlark-safe value.

    Primitives, dicts (with string keys) and lists are kept as-is (recursed).
    Everything else is wrapped in an ``OpaquePythonObject`` so it can be passed
    through Starlark without triggering JSON serialisation.
    """
    if isinstance(obj, _STARLARK_PRIMITIVES):
        return obj
    if isinstance(obj, starlark.OpaquePythonObject):
        return obj  # already wrapped
    if isinstance(obj, dict):
        return {k: to_starlark(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_starlark(item) for item in obj]
    return starlark.OpaquePythonObject(obj)


def from_starlark(obj: Any) -> Any:
    """Recursively convert a Starlark value back to a plain Python object.

    ``OpaquePythonObject`` instances are unwrapped; primitives, dicts and lists
    are recursed into.
    """
    if isinstance(obj, _STARLARK_PRIMITIVES):
        return obj
    if isinstance(obj, starlark.OpaquePythonObject):
        # When starlark-pyo3 passes an OpaquePythonObject back to Python the
        # original object reappears automatically, but if we receive the
        # wrapper type itself we just return it as-is (it *is* the original).
        return obj
    if isinstance(obj, dict):
        return {k: from_starlark(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [from_starlark(item) for item in obj]
    return obj
