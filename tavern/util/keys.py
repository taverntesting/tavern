import logging

from . import exceptions


logger = logging.getLogger(__name__)


def check_expected_keys(expected, actual):

    keyset = set(actual)

    if not keyset <= expected:
        unexpected = keyset - expected

        msg = "Unexpected keys {}".format(unexpected)
        logger.error(msg)
        raise exceptions.UnexpectedKeysError(msg)
