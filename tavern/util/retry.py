from functools import wraps
import logging

from . import exceptions
from .delay import delay

logger = logging.getLogger(__name__)


def retry(stage, test_block_config):
    """Look for retry and try to repeat the stage `retry` times.

    Args:
        test_block_config (dict): Configuration for current test
        stage (dict): test stage
    """

    max_retries = stage.get("max_retries", 0)

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
