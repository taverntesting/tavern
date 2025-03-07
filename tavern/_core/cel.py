import logging

import celpy

from tavern._core import exceptions
from tavern._core.dict_util import format_keys
from tavern._core.pytest.config import TestConfig

logger: logging.Logger = logging.getLogger(__name__)


def run_cel(content: str, test_block_config: TestConfig) -> bool:
    """Run a CEL (Common Expression Language) program to determine if a test should be skipped.

    Args:
        content: The unformatted CEL string to evaluate
        test_block_config: Configuration containing variables to use in CEL evaluation

    Returns:
        Result of CEL evaluation

    Raises:
        CELError: If CEL program is invalid, or variables cannot be converted to CEL types
    """

    formatted = format_keys(content, test_block_config.variables)

    logger.debug("CEL program to evalute: %s", formatted)

    env = celpy.Environment()
    try:
        ast = env.compile(formatted)
    except celpy.CELParseError as e:
        raise exceptions.CELError(
            f"unable to parse '{formatted}' as CEL",
        ) from e

    try:
        variables = celpy.json_to_cel(test_block_config.variables)
    except ValueError as e:
        raise exceptions.CELError("unable to convert variables to CEL variables") from e

    # Is there a better way to do this?
    variables["True"] = celpy.json_to_cel(True)
    variables["False"] = celpy.json_to_cel(False)

    try:
        result = env.program(ast).evaluate(variables)
    except celpy.CELEvalError as e:
        raise exceptions.CELError(
            "Error evaluating CEL program (missing variables?)"
        ) from e

    if not isinstance(result, (celpy.celtypes.BoolType, type(None))):
        raise exceptions.CELError(
            f"'skip' CEL program did not evaluate to True/False (got {result} of type {type(result)})",
        )

    return bool(result)
