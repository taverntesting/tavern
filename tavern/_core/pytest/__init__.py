from .hooks import pytest_addhooks, pytest_addoption, pytest_collect_file
from .newhooks import call_hook
from .util import add_parser_options

__all__ = [
    "add_parser_options",
    "call_hook",
    "pytest_addhooks",
    "pytest_addoption",
    "pytest_collect_file",
    "starlark_collect_file",
]


def starlark_collect_file(parent, file_path):
    """Collect starlark pipeline files."""
    from tavern._core.starlark.pytest_plugin import starlark_collect_file as collect

    return collect(parent, file_path)
