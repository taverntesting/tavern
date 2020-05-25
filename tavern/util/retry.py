from functools import wraps
import logging

from . import exceptions
from .delay import delay
from .dict_util import format_keys

logger = logging.getLogger(__name__)


def retry(stage, test_block_config):
    """Look for retry and try to repeat the stage `retry` times.

    Args:
        test_block_config (dict): Configuration for current test
        stage (dict): test stage
    """

    if "max_retries" in stage:
        max_retries = maybe_format_max_retries(
            stage.get("max_retries"), test_block_config
        )
    else:
        max_retries = 0

    if max_retries == 0:

        def catch_wrapper(fn):
            @wraps(fn)
            def wrapped(*args, **kwargs):
                res = fn(*args, **kwargs)
                logger.debug("Stage '%s' succeeded.", stage["name"])
                return res

            return wrapped

        return catch_wrapper
    else:

        def retry_wrapper(fn):
            @wraps(fn)
            def wrapped(*args, **kwargs):
                i = 0
                res = None
                for i in range(max_retries + 1):
                    try:
                        res = fn(*args, **kwargs)
                    except exceptions.BadSchemaError:
                        raise
                    except exceptions.TavernException as e:
                        if i < max_retries:
                            logger.info(
                                "Stage '%s' failed for %i time. Retrying.",
                                stage["name"],
                                i + 1,
                            )
                            delay(stage, "after", test_block_config["variables"])
                        else:
                            logger.error(
                                "Stage '%s' did not succeed in %i retries.",
                                stage["name"],
                                max_retries,
                            )

                            if isinstance(e, exceptions.TestFailError):
                                raise
                            else:
                                raise exceptions.TestFailError(
                                    "Test '{}' failed: stage did not succeed in {} retries.".format(
                                        stage["name"], max_retries
                                    )
                                ) from e
                    else:
                        break

                logger.debug("Stage '%s' succeed after %i retries.", stage["name"], i)
                return res

            return wrapped

        return retry_wrapper


def maybe_format_max_retries(max_retries, test_block_config):
    """Possibly handle max_retries validation"""

    # Probably a format variable, or just invalid (in which case it will fail further down)
    max_retries = format_keys(max_retries, test_block_config["variables"])

    # Missing type token will mean that max_retries is still a string and will fail here
    # Could auto convert here as well, but keep it consistent and just fail
    if not isinstance(max_retries, int):
        raise exceptions.InvalidRetryException(
            "Invalid type for max_retries - was {}".format(type(max_retries))
        )

    if max_retries < 0:
        raise exceptions.InvalidRetryException("max_retries must be greater than 0")

    return max_retries
