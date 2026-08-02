"""Evaluation of single Starlark expressions embedded in a stage.

This is used for the per-stage ``if``, ``retry_until`` and ``fail_if`` keys, which are a
much lighter-weight alternative to writing a whole ``control_flow`` script. Like the
simpleeval based ``skip`` key, expressions here are format-string interpolated before
being evaluated, so ``if: "{var_x} > 2"`` is the way to refer to a test variable.

An 'expression' can also be several statements long, in which case the value of the last
one is what decides the result. The helper modules can be loaded as in a ``control_flow``
script, but ``run_stage`` is not available - there is already a stage being run.

This module must not import anything from tavern._core.run, and must not import
starlark at the top level, so that it can be imported (lazily) from the normal
non-starlark test path.
"""

import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from tavern._core import exceptions
from tavern._core.dict_util import format_keys

if TYPE_CHECKING:
    import starlark

    from tavern._core.pytest.config import TestConfig

logger: logging.Logger = logging.getLogger(__name__)

# Name the response dict is bound to before being turned into a struct
_RESPONSE_DICT_NAME = "__tavern_response"

_RESPONSE_PRELUDE = f"response = struct(**{_RESPONSE_DICT_NAME})"


def _import_starlark():
    """Import the starlark module, raising a useful error if it isn't installed"""
    try:
        import starlark
    except ImportError as e:
        raise exceptions.DependencyMissingError(
            "starlark", "pip install tavern[scriptable]"
        ) from e

    return starlark


def _get_dialect() -> "starlark.Dialect":
    starlark = _import_starlark()
    dialect = starlark.Dialect.extended()
    dialect.enable_keyword_only_arguments = True
    return dialect


def _get_globals() -> "starlark.Globals":
    starlark = _import_starlark()
    return starlark.Globals.standard().extended_by(
        [
            starlark.LibraryExtension.StructType,
        ]
    )


def _get_file_loader(
    module_globals: "starlark.Globals", dialect: "starlark.Dialect"
) -> "starlark.FileLoader":
    """Get a loader which makes the tavern helper modules available to an expression

    This is the same set of helpers as in a 'control_flow' script, except that
    'run_stage' can't do anything - the stage the expression is attached to is already
    being run.

    Args:
        module_globals: globals to evaluate the helpers with
        dialect: dialect to parse the helpers with

    Returns:
        a loader which handles '@tavern_helpers.star'
    """
    starlark = _import_starlark()

    from .builtins import (
        add_library_callables,
        add_unavailable_run_stage,
        get_starlark_builtins,
    )

    # The return type is a starlark.FrozenModule, but the name is shadowed by the
    # local import above
    def load(filename: str) -> Any:
        if filename != "@tavern_helpers.star":
            raise FileNotFoundError(filename)

        helpers = starlark.Module()
        add_library_callables(helpers)
        add_unavailable_run_stage(
            helpers,
            "'run_stage' is not available in a per-stage expression - use a "
            "'control_flow' script if you need to run another stage",
        )
        ast = starlark.parse(filename, get_starlark_builtins(), dialect=dialect)
        starlark.eval(helpers, ast, module_globals)

        return helpers.freeze()

    return starlark.FileLoader(load)


def eval_stage_expression(
    key: str,
    expr: str,
    stage: Mapping[str, Any],
    test_block_config: "TestConfig",
    *,
    response: Mapping[str, Any] | None = None,
) -> bool:
    """Evaluate the Starlark expression from a per-stage 'if' or 'retry_until' key

    Args:
        key: name of the stage key the expression came from
        expr: the Starlark expression
        stage: the stage it came from, used for error messages
        test_block_config: current test config, the variables from which are bound as
            globals in the expression
        response: response values to bind as a 'response' struct, if any

    Returns:
        the result of the expression

    Raises:
        exceptions.UnexpectedKeysError: if the experimental starlark pipeline was not enabled
        exceptions.EvalError: if the expression could not be run, or did not evaluate to
            a boolean
    """
    if not test_block_config.experimental_starlark_pipeline:
        raise exceptions.UnexpectedKeysError(
            f"'{key}' requires the experimental starlark pipeline to be enabled - pass "
            "--tavern-experimental-starlark-pipeline or set "
            "tavern-experimental-starlark-pipeline in your pytest ini file"
        )

    return eval_expression(
        expr,
        test_block_config.variables,
        response=response,
        description=f"'{key}' in stage '{stage.get('name', 'unnamed-stage')}'",
    )


def eval_response_expression(
    key: str,
    expr: str,
    stage: Mapping[str, Any],
    test_block_config: "TestConfig",
    *,
    response: Any,
    success: bool,
    request_vars: Mapping[str, Any],
) -> bool:
    """Evaluate a stage expression which can also inspect the response from the stage

    This is used for the 'retry_until' and 'fail_if' keys, which both get a 'response'
    struct bound in the expression.

    Args:
        key: name of the stage key the expression came from
        expr: the Starlark expression
        stage: the stage it came from
        test_block_config: current test config
        response: the response from running the stage, if any
        success: whether the stage passed all of its verifications
        request_vars: any variables captured during the request

    Returns:
        the result of the expression

    Raises:
        exceptions.BadSchemaError: if the expression was not a string
    """
    from .response_struct import create_response_struct

    if not isinstance(expr, str):
        raise exceptions.BadSchemaError(
            f"Unexpected '{type(expr)}' in {key} key - should be a string"
        )

    response_values = create_response_struct(
        response,
        success=success,
        request_vars=dict(request_vars),
        stage_name=stage.get("name", "unnamed-stage"),
    )

    return eval_stage_expression(
        key,
        expr,
        stage,
        test_block_config,
        response=response_values,
    )


def eval_expression(
    expr: str,
    variables: Mapping[str, Any],
    *,
    response: Mapping[str, Any] | None = None,
    description: str,
) -> bool:
    """Evaluate a Starlark expression, interpolating the given variables into it first

    Args:
        expr: the Starlark expression to evaluate, which may contain format strings
            referring to test variables
        variables: test variables to interpolate into the expression
        response: if given, a dict of response values (see
            :func:`tavern._core.starlark.response_struct.create_response_struct`) which
            is bound as a struct called 'response'
        description: what this expression is, used in error messages

    Returns:
        the result of the expression

    Raises:
        exceptions.EvalError: if the expression could not be formatted or run, or if it
            did not evaluate to a boolean
    """
    starlark = _import_starlark()

    from .types import from_starlark, to_starlark

    try:
        formatted = format_keys(expr, variables)
    except exceptions.MissingFormatError as e:
        raise exceptions.EvalError(
            f"Undefined variable used in Starlark expression for {description}: {expr}"
        ) from e

    dialect = _get_dialect()
    module = starlark.Module()
    module_globals = _get_globals()

    if response is not None:
        module[_RESPONSE_DICT_NAME] = to_starlark(dict(response))
        prelude = starlark.parse(description, _RESPONSE_PRELUDE, dialect=dialect)
        starlark.eval(module, prelude, module_globals)

    try:
        ast = starlark.parse(description, formatted, dialect=dialect)
    except starlark.StarlarkError as e:
        raise exceptions.EvalError(
            f"Error parsing Starlark expression for {description}: {formatted} "
            f"(from {expr})"
        ) from e

    logger.debug(
        "Evaluating Starlark expression for %s: %s (from %s)",
        description,
        formatted,
        expr,
    )

    try:
        result = starlark.eval(
            module, ast, module_globals, _get_file_loader(module_globals, dialect)
        )
    except starlark.StarlarkError as e:
        raise exceptions.EvalError(
            f"Error evaluating Starlark expression for {description}: {formatted} "
            f"(from {expr}) ({e})"
        ) from e

    result = from_starlark(result)

    if not isinstance(result, bool):
        raise exceptions.EvalError(
            f"Starlark expression for {description} did not evaluate to True/False "
            f"(got {result} of type {type(result)}): {formatted} (from {expr})"
        )

    return result
