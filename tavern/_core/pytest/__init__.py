"""
Tavern Pytest Integration Module

This module provides pytest integration for the Tavern testing framework.
It handles the integration between Tavern and pytest for test discovery and execution.

The module contains the pytest plugin components that enable Tavern
to work seamlessly with pytest for test discovery, execution, and reporting.
"""

from .hooks import pytest_addhooks, pytest_addoption, pytest_collect_file
from .newhooks import call_hook
from .util import add_parser_options

__all__ = [
    "add_parser_options",
    "call_hook",
    "pytest_addhooks",
    "pytest_addoption",
    "pytest_collect_file",
]
