import logging
import time

logger = logging.getLogger(__name__)


def inject_context(func):
    """Decorates the given function for passing the current test context. This
    decorator should be used for callbacks in the before- and after stages
    in a test.

    Callbacks will receive a dictionary `context` as parameter which can be
    used for saving values between function calls. A common use case would be
    a setup and teardown pattern between before- and after-stage callbacks.

    Additionally, the context contains the saved variables in the field
    `variables`.
    """
    # pylint: disable=protected-access
    func._tavern_inject_context = True
    return func


def delay(seconds):
    """Helper function which delays current execution by :param:`seconds`
    seconds."""

    logger.debug("Delaying request for %d seconds", seconds)
    time.sleep(seconds)
