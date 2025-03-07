import logging
import simpleeval

from tavern._core import exceptions
from tavern._core.dict_util import format_keys
from tavern._core.pytest.config import TestConfig

logger: logging.Logger = logging.getLogger(__name__)


def eval_skip(content: str, test_block_config: TestConfig) -> bool:
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

    result = simpleeval.simple_eval(formatted, names=test_block_config.variables)
    if not isinstance(result, (bool, None)):
        raise exceptions.BadSchemaError(
            f"'skip' program did not evaluate to True/False (got {result} of type {type(result)})",
        )

    return bool(result)
