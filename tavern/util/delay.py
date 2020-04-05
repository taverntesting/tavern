import logging
import time

from .dict_util import format_keys

logger = logging.getLogger(__name__)


def delay(stage, when, variables):
    """Look for delay_before/delay_after and sleep

    Args:
        stage (dict): test stage
        when (str): 'before' or 'after'
        variables (dict): Variables to format with
    """

    try:
        length = format_keys(stage["delay_{}".format(when)], variables)
    except KeyError:
        pass
    else:
        logger.debug("Delaying %s request for %.2f seconds", when, length)
        time.sleep(length)
