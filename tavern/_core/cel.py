import logging

import celpy

from tavern._core import exceptions
from tavern._core.pytest.config import TestConfig

logger: logging.Logger = logging.getLogger(__name__)


def run_cel(content: str, formatted: str, test_block_config: TestConfig) -> bool | None:
    """Run a CEL (Common Expression Language) program to determine if a test should be skipped.

    Args:
        content: The raw CEL content before formatting
        formatted: The formatted CEL string to evaluate
        test_block_config: Configuration containing variables to use in CEL evaluation

    Returns:
        bool | None: Result of CEL evaluation. If result is False, test will be skipped.

    Raises:
        BadSchemaError: If CEL program is invalid, or variables cannot be converted to CEL types
    """
    logger.debug("CEL program to evalute: %s", formatted)

    env = celpy.Environment()
    try:
        ast = env.compile(formatted)
    except celpy.CELParseError as e:
        raise exceptions.BadSchemaError(
            f"unable to parse '{content}' as CEL",
        ) from e

    try:
        variables = celpy.json_to_cel(test_block_config.variables)
    except ValueError as e:
        raise exceptions.BadSchemaError(
            "unable to convert variables to CEL variables"
        ) from e

    try:
        result = env.program(ast).evaluate(variables)
    except celpy.CELEvalError as e:
        raise exceptions.BadSchemaError(
            "Error evaluating CEL program (missing variables?)"
        ) from e

    if not isinstance(result, (celpy.celtypes.BoolType, type(None))):
        raise exceptions.BadSchemaError(
            f"'skip' CEL program did not evaluate to True/False (got {result} of type {type(result)})",
        )

    return result
