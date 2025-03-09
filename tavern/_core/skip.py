import logging

import simpleeval

from tavern._core import exceptions
from tavern._core.dict_util import format_keys
from tavern._core.pytest.config import TestConfig

logger: logging.Logger = logging.getLogger(__name__)

functions = simpleeval.DEFAULT_FUNCTIONS.copy()
functions["len"] = len


def eval_skip(content: str, test_block_config: TestConfig) -> bool:
    """Run a simpleeval expression to determine if a test should be skipped.

    Args:
        content: The unformatted simpleeval string to evaluate
        test_block_config: Configuration containing variables to use in simpleeval evaluation

    Returns:
        Result of simpleeval evaluation

    Raises:
        exceptions.BadSchemaError: If simpleeval expression is invalid

    """

    formatted = format_keys(content, test_block_config.variables)

    logger.debug("simpleeval expression to evaluate: %s", formatted)

    try:
        result = simpleeval.simple_eval(
            formatted, names=test_block_config.variables, functions=functions
        )
    except simpleeval.NameNotDefined as e:
        raise exceptions.EvalError("Undefined variable used in program") from e
    except TypeError as e:
        raise exceptions.EvalError("Error running program") from e

    if not isinstance(result, bool | type(None)):
        raise exceptions.EvalError(
            f"'skip' program did not evaluate to True/False (got {result} of type {type(result)})",
        )

    return bool(result)
