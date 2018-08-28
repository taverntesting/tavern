import logging
from functools import wraps

from future.utils import raise_from

from . import exceptions
from .delay import delay

logger = logging.getLogger(__name__)


def retry(stage):
    """Look for retry and try to repeat the stage `retry` times.

    Args:
        stage (dict): test stage
    """

    n_repeats = stage.get('retry', 1)

    def decorator(fn):
        @wraps(fn)
        def wrapped(*args, **kwargs):
            exception = NotImplementedError('not reached')
            for i in range(1, n_repeats + 1):
                try:
                    res = fn(*args, **kwargs)
                except exceptions.TavernException as e:
                    exception = e
                    logger.info('Stage %s failed for %i time. Retrying.', stage['name'], i)
                    delay(stage, 'after')
                else:
                    break
            else:
                logger.error('Stage %s did not succeed in %i repeats.', stage['name'], n_repeats)
                raise_from(
                    exceptions.TestFailError(
                        "Test '{}' failed: stage did not succeed in {} repeats.".format(stage['name'], n_repeats)),
                    exception)
            logger.debug('Stage %s succeed after %i repeats.', stage['name'], i)  # pylint: disable=undefined-loop-variable
            return res

        return wrapped

    return decorator
