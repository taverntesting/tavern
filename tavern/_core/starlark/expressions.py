"""Evaluation of single Starlark expressions embedded in a stage.

This is used for the per-stage ``if`` and ``retry_until`` keys, which are a much
lighter-weight alternative to writing a whole ``control_flow`` script. Unlike the
simpleeval based ``skip`` key, expressions here are _not_ format-string interpolated -
variables are bound directly as Starlark globals, so ``if: var_x > 2`` works but
``if: "{var_x} > 2"`` does not.

This module must not import anything from tavern._core.run, and must not import
starlark at the top level, so that it can be imported (lazily) from the normal
non-starlark test path.
"""

import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any

from tavern._core import exceptions

if TYPE_CHECKING:
    import starlark

    from tavern._core.pytest.config import TestConfig

logger: logging.Logger = logging.getLogger(__name__)

# Reserved words in Starlark which can't be used as variable names. Anything in the
# available variables which clashes with one of these is just not bound.
_STARLARK_RESERVED = frozenset(
    {
        "and",
        "break",
        "continue",
        "def",
        "elif",
        "else",
        "for",
        "if",
        "in",
        "lambda",
        "load",
        "not",
        "or",
        "pass",
        "return",
        "while",
        # Reserved for future use by the spec
        "as",
        "assert",
        "class",
        "del",
        "except",
        "finally",
        "from",
        "global",
        "import",
        "is",
        "nonlocal",
        "raise",
        "try",
        "with",
        "yield",
    }
)

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


def parse_expression(expr: str, description: str) -> None:
    """Check that an expression parses, without running it

    Args:
        expr: the Starlark expression
        description: what this expression is, used in error messages

    Raises:
        exceptions.BadSchemaError: if it could not be parsed
    """
    starlark = _import_starlark()

    try:
        starlark.parse(description, expr, dialect=_get_dialect())
    except starlark.StarlarkError as e:
        raise exceptions.BadSchemaError(
            f"Failed to parse Starlark expression for {description}: {expr}"
        ) from e


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


def eval_expression(
    expr: str,
    variables: Mapping[str, Any],
    *,
    response: Mapping[str, Any] | None = None,
    description: str,
) -> bool:
    """Evaluate a Starlark expression with the given variables bound as globals

    Args:
        expr: the Starlark expression to evaluate
        variables: test variables to bind as globals. Any key which is not a valid
            Starlark identifier is skipped.
        response: if given, a dict of response values (see
            :func:`tavern._core.starlark.response_struct.create_response_struct`) which
            is bound as a struct called 'response'
        description: what this expression is, used in error messages

    Returns:
        the result of the expression

    Raises:
        exceptions.EvalError: if the expression could not be run, or if it did not
            evaluate to a boolean
    """
    starlark = _import_starlark()

    from .types import from_starlark, to_starlark

    dialect = _get_dialect()
    module = starlark.Module()
    module_globals = _get_globals()

    for name, value in variables.items():
        if not isinstance(name, str) or not name.isidentifier():
            logger.debug(
                "Not binding variable '%s' in %s - not a valid identifier",
                name,
                description,
            )
            continue
        if name in _STARLARK_RESERVED:
            logger.debug(
                "Not binding variable '%s' in %s - reserved word in Starlark",
                name,
                description,
            )
            continue

        module[name] = to_starlark(value)

    if response is not None:
        module[_RESPONSE_DICT_NAME] = to_starlark(dict(response))
        prelude = starlark.parse(description, _RESPONSE_PRELUDE, dialect=dialect)
        starlark.eval(module, prelude, module_globals)

    try:
        ast = starlark.parse(description, expr, dialect=dialect)
    except starlark.StarlarkError as e:
        raise exceptions.EvalError(
            f"Error parsing Starlark expression for {description}: {expr}"
        ) from e

    logger.debug("Evaluating Starlark expression for %s: %s", description, expr)

    try:
        result = starlark.eval(module, ast, module_globals)
    except starlark.StarlarkError as e:
        raise exceptions.EvalError(
            f"Error evaluating Starlark expression for {description}: {expr} ({e})"
        ) from e

    result = from_starlark(result)

    if not isinstance(result, bool):
        raise exceptions.EvalError(
            f"Starlark expression for {description} did not evaluate to True/False "
            f"(got {result} of type {type(result)}): {expr}"
        )

    return result
