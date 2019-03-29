import logging

from collections.abc import Mapping

from abc import abstractmethod

from textwrap import indent
from tavern.util.dict_util import format_keys, check_keys_match_recursive

logger = logging.getLogger(__name__)


def indent_err_text(err):
    if err == "null":
        err = "<No body>"
    return indent(err, " " * 4)


class BaseResponse(object):
    def __init__(self):
        # all errors in this response
        self.errors = []

        # None by default?
        self.test_block_config = {"variables": {}}

    def _str_errors(self):
        return "- " + "\n- ".join(self.errors)

    def _adderr(self, msg, *args, **kwargs):
        e = kwargs.get("e")

        if e:
            logger.exception(msg, *args)
        else:
            logger.error(msg, *args)
        self.errors += [(msg % args)]

    @abstractmethod
    def verify(self, response):
        """Verify response against expected values and returns any values that
        we wanted to save for use in future requests
        """

    def recurse_check_key_match(self, expected_block, block, blockname, strict):
        """Valid returned data against expected data

        Todo:
            Optionally use a validation library too

        Args:
            expected_block (dict): expected data
            block (dict): actual data
            blockname (str): 'name' of this block (params, mqtt, etc) for error messages
        """

        if not expected_block:
            logger.debug("No expected %s to check against", blockname)
            return

        expected_block = format_keys(
            expected_block, self.test_block_config["variables"]
        )

        if block is None:
            self._adderr(
                "expected %s in the %s, but there was no response %s",
                expected_block,
                blockname,
                blockname,
            )
            return

        if isinstance(block, Mapping):
            block = dict(block)

        logger.debug("expected = %s, actual = %s", expected_block, block)

        check_keys_match_recursive(expected_block, block, [], strict)
