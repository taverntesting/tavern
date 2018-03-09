import logging
import warnings
from abc import abstractmethod

from future.utils import raise_from

from tavern.util import exceptions
from tavern.util.loader import ANYTHING
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

    def _check_response_keys_recursive(self, expected_val, actual_val, keys):
        """Utility to recursively check response values

        expected and actual both have to be of the same type or it will raise an
        error.

        Todo:
            This could be turned into a single-dispatch function for cleaner
            code and to remove a load of the isinstance checks

        Args:
            expected_val (dict, str): expected value
            actual_val (dict, str): actual value
        """

        def full_err():
            """Get error in the format:

            a["b"]["c"] = 4, b["b"]["c"] = {'key': 'value'}

            """
            def _format_err(which):
                return "{}{}".format(which, "".join('["{}"]'.format(key) for key in keys))

            e_formatted = _format_err("expected")
            a_formatted = _format_err("actual")
            return "{} = '{}', {} = '{}'".format(e_formatted, expected_val,
                a_formatted, actual_val)

        actual_is_dict = isinstance(actual_val, dict)
        expected_is_dict = isinstance(expected_val, dict)
        if (actual_is_dict and not expected_is_dict) or (expected_is_dict and not actual_is_dict):
            raise exceptions.KeyMismatchError("Structure of returned data was different than expected ({})".format(full_err()))

        if isinstance(expected_val, dict):
            if set(expected_val.keys()) != set(actual_val.keys()):
                raise exceptions.KeyMismatchError("Structure of returned data was different than expected ({})".format(full_err()))

            for key in expected_val:
                self._check_response_keys_recursive(expected_val[key], actual_val[key], keys + [key])
        else:
            try:
                assert actual_val == expected_val
            except AssertionError as e:
                if expected_val is None:
                    warnings.warn("Expected value was 'null', so this check will pass - this will be removed in a future version. IF you want to check against 'any' value, use '!anything' instead.", RuntimeWarning)
                elif expected_val is ANYTHING:
                    logger.debug("Actual value = '%s' - matches !anything", actual_val)
                else:
                    raise_from(exceptions.KeyMismatchError("Key mismatch: ({})".format(full_err())), e)

    def recurse_check_key_match(self, expected_block, block, blockname):
        """Valid returned data against expected data

        Todo:
            Optionally use a validation library too

        Args:
            expected_block (dict): expected data
            block (dict): actual data
            blockname (str): 'name' of this block (params, mqtt, etc) for error messages
        """

        if not expected_block:
            logger.debug("Nothing to check against")
            return

        expected_block = format_keys(expected_block, self.test_block_config["variables"])

        if block is None:
            self._adderr("expected %s in the %s, but there was no response body",
                expected_block, blockname)
            return

        logger.debug("expected = %s, actual = %s", expected_block, block)

        for split_key, joined_key, expected_val in yield_keyvals(expected_block):
            try:
                actual_val = recurse_access_key(block, split_key)
            except KeyError as e:
                self._adderr("Key not present: %s", joined_key, e=e)
                continue

            logger.debug("%s: %s vs %s", joined_key, expected_val, actual_val)

            try:
                self._check_response_keys_recursive(expected_val, actual_val, [])
            except exceptions.KeyMismatchError as e:
                logger.error("Key mismatch on %s", joined_key)
                self._adderr("Value mismatch: got '%s' (type: %s), expected '%s' (type: %s)",
                    actual_val, type(actual_val), expected_val, type(expected_val), e=e)
            else:
                logger.debug("Key %s was present and matched", joined_key)
