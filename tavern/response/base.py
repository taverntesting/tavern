import logging
from abc import abstractmethod

from tavern.util.python_2_util import indent
from tavern.util.dict_util import format_keys, recurse_access_key, yield_keyvals

logger = logging.getLogger(__name__)


def indent_err_text(err):
    if err == "null":
        err = "<No body>"
    return indent(err, " "*4)


class BaseResponse(object):

    def __init__(self):
        # all errors in this response
        self.errors = []

        # None by default?
        self.test_block_config = {}

    def _str_errors(self):
        return "- " + "\n- ".join(self.errors)

    def _adderr(self, msg, *args, **kwargs):
        e = kwargs.get('e')

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

    def recurse_check_key_match(self, expected_block, block, blockname):
        """Valid returned data against expected data

        Todo:
            Optionally use a validation library too

        Args:
            expected_block (dict): expected data
            block (dict): actual data
            blockname (str): 'name' of this block (params, mqtt, etc) for error messages
        """

        if expected_block:
            expected_block = format_keys(expected_block, self.test_block_config["variables"])

            if block is None:
                self._adderr("expected %s in the %s, but there was no response body",
                    expected_block, blockname)
            else:
                logger.debug("expected = %s, actual = %s", expected_block, block)
                for split_key, joined_key, expected_val in yield_keyvals(expected_block):
                    try:
                        actual_val = recurse_access_key(block, split_key)
                    except KeyError as e:
                        self._adderr("Key not present: %s", joined_key, e=e)
                        continue

                    logger.debug("%s: %s vs %s", joined_key, expected_val, actual_val)

                    try:
                        assert actual_val == expected_val
                    except AssertionError as e:
                        if expected_val != None:
                            self._adderr("Value mismatch: got '%s' (type: %s), expected '%s' (type: %s)",
                                actual_val, type(actual_val), expected_val, type(expected_val), e=e)
                        else:
                            logger.debug("Key %s was present", joined_key)
