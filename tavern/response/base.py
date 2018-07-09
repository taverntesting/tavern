import logging
import collections
from abc import abstractmethod
import warnings

from tavern.util import exceptions
from tavern.util.python_2_util import indent
from tavern.util.dict_util import format_keys, check_keys_match_recursive

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
        self.test_block_config = {"variables": {}}

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

        expected_block = format_keys(expected_block, self.test_block_config["variables"])

        if block is None:
            self._adderr("expected %s in the %s, but there was no response %s",
                expected_block, blockname, blockname)
            return

        if isinstance(block, collections.Mapping):
            block = dict(block)

        logger.debug("expected = %s, actual = %s", expected_block, block)

        try:
            check_keys_match_recursive(expected_block, block, [], strict)
        except exceptions.KeyMismatchError as e:
            # TODO
            # This block be removed in 1.0 as it is a breaking API change, and
            # replaced with a simple self._adderr. This is just here to maintain
            # 'legacy' key checking which was in fact broken.

            if strict:
                logger.debug("Failing because 'strict' was true")
                # This should always raise an error
                self._adderr("Value mismatch in %s: %s", blockname, e)
                return

            if blockname != "body":
                logger.debug("Failing because it isn't the body")
                # This should always raise an error
                self._adderr("Value mismatch in %s: %s", blockname, e)
                return

            if not isinstance(expected_block, type(block)):
                logger.debug("Failing because it was a type mismatch")
                # This should always raise an error
                self._adderr("Value mismatch in %s: %s", blockname, e)
                return

            if isinstance(block, list):
                logger.debug("Failing because its a list")
                # This should always raise an error
                self._adderr("Value mismatch in %s: %s", blockname, e)
                return

            # At this point it will always be a dict - run the check again just
            # matching the top level keys then run it again on each individual
            # item, like it ran before.
            c_expected = {i: None for i in expected_block}
            c_actual = {i: None for i in block}
            try:
                check_keys_match_recursive(c_expected, c_actual, [], strict=False)

                # An error will be raised above if there are more expected keys
                # than returned. At this point we might have more returned that
                # expected, so fall back to 'legacy' behaviour
                for k, v in expected_block.items():
                    check_keys_match_recursive(v, block[k], [k], strict=True)
            except exceptions.KeyMismatchError:
                self._adderr("Value mismatch in %s: %s", blockname, e)
            else:
                msg = "Checking keys worked using 'legacy' comparison, which will not match dictionary keys at the top level of the response. This behaviour will be changed in a future version"
                warnings.warn(msg, FutureWarning)
                logger.warning(msg, exc_info=True)
