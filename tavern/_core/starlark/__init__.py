"""Starlark pipeline support for Tavern.

This must not import anything which needs starlark, so that a missing 'scriptable' extra
is reported by expressions.import_starlark instead of as an ImportError.
"""
