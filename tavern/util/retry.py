import logging
from functools import wraps

from future.utils import raise_from

from . import exceptions
from .delay import delay

logger = logging.getLogger(__name__)


def retry(stage, test_block_config):
    """Look for retry and try to repeat the stage `retry` times.

    Args:
        stage (dict): test stage
    """

    max_retries = stage.get("max_retries", 0)

    if max_retries == 0:
        # Just return the plain function
        return lambda fn: fn

    def retry_wrapper(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            i = 0
            for i in range(max_retries + 1):
                try:
                    res = fn(*args, **kwargs)
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
                        raise_from(
                            exceptions.TestFailError(
                                "Test '{}' failed: stage did not succeed in {} retries.".format(
                                    stage["name"], max_retries
                                )
                            ),
                            e,
                        )
                else:
                    break

            logger.debug("Stage '%s' succeed after %i retries.", stage["name"], i)
            return res

        return wrapped

    return retry_wrapper
