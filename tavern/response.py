from abc import abstractmethod
from collections.abc import Mapping
import logging
from textwrap import indent
import traceback

from tavern._core import exceptions
from tavern._core.dict_util import check_keys_match_recursive, recurse_access_key
from tavern._core.extfunctions import get_wrapped_response_function

logger = logging.getLogger(__name__)


def indent_err_text(err):
    if err == "null":
        err = "<No body>"
    return indent(err, " " * 4)


class BaseResponse(object):
    def __init__(self, name, expected, test_block_config):
        self.name = name

        # all errors in this response
        self.errors = []

        self.validate_functions = []
        self._check_for_validate_functions(expected)

        self.test_block_config = test_block_config

        self.expected = expected

        self.response = None

    def _str_errors(self):
        return "- " + "\n- ".join(self.errors)

    def _adderr(self, msg, *args, e=None):
        if e:
            logger.exception(msg, *args)
        else:
            logger.error(msg, *args)
        self.errors += [(msg % args)]

    @abstractmethod
    def verify(self, response):
        """Verify response against expected values and returns any values that
        we wanted to save for use in future requests

        It is expected that anything subclassing this can throw an exception indicating that the response
        verification failed.
        """

    def recurse_check_key_match(self, expected_block, block, blockname, strict):
        """Valid returned data against expected data

        Todo:
            Optionally use a validation library too

        Args:
            strict: strictness setting for this block
            expected_block (dict): expected data
            block (dict): actual data
            blockname (str): 'name' of this block (params, mqtt, etc) for error messages
        """

        if expected_block is None:
            logger.debug("No expected %s to check against", blockname)
            return

        # This should be done _before_ it gets to this point - typically in get_expected_from_request from plugin
        # expected_block = format_keys(
        #     expected_block, self.test_block_config.variables
        # )

        if block is None:
            if not expected_block:
                logger.debug(
                    "No %s in response to check, but not erroring because expected was %s",
                    blockname,
                    expected_block,
                )
                return

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

        try:
            check_keys_match_recursive(expected_block, block, [], strict)
        except exceptions.KeyMismatchError as e:
            self._adderr(e.args[0], e=e)

    def _check_for_validate_functions(self, response_block):
        """
        See if there were any functions specified in the response block and save them for later use

        Args:
            response_block (dict): block of external functions to call
        """

        def check_ext_functions(verify_block):
            if isinstance(verify_block, list):
                for vf in verify_block:
                    self.validate_functions.append(get_wrapped_response_function(vf))
            elif isinstance(verify_block, dict):
                self.validate_functions.append(
                    get_wrapped_response_function(verify_block)
                )
            elif verify_block is not None:
                raise exceptions.BadSchemaError(
                    "Badly formatted 'verify_response_with' block"
                )

        check_ext_functions(response_block.get("verify_response_with", None))

        def check_deprecated_validate(name):
            nfuncs = len(self.validate_functions)
            block = response_block.get(name, {})
            if isinstance(block, dict):
                check_ext_functions(block.get("$ext", None))
                if nfuncs != len(self.validate_functions):
                    raise exceptions.InvalidExtBlockException(
                        name,
                    )

        # Could put in an isinstance check here
        check_deprecated_validate("json")

    def _maybe_run_validate_functions(self, response):
        """Run validation functions if available

        Note:
             'response' will be different depending on where this is called from

        Args:
            response (object): Response type. This could be whatever the response type/plugin uses.
        """
        logger.debug(
            "Calling ext function from '%s' with response '%s'", type(self), response
        )

        for vf in self.validate_functions:
            try:
                vf(response)
            except Exception as e:  # pylint: disable=broad-except
                self._adderr(
                    "Error calling validate function '%s':\n%s",
                    vf.func,
                    indent_err_text(traceback.format_exc()),
                    e=e,
                )

    def maybe_get_save_values_from_ext(self, response, expected):
        """If there is an $ext function in the save block, call it and save the response

        Args:
            expected (dict): the expected response (incl body/json/headers/mqtt topic/etc etc)
                Actual contents depends on which type of response is being checked
            response (object): response object.
                Actual contents depends on which type of response is being checked

        Returns:
            dict: mapping of name: value of things to save
        """
        try:
            wrapped = get_wrapped_response_function(expected["save"]["$ext"])
        except KeyError:
            logger.debug("No save function for this stage")
            return {}

        try:
            to_save = wrapped(response)
        except Exception as e:  # pylint: disable=broad-except
            self._adderr(
                "Error calling save function '%s':\n%s",
                wrapped.func,
                indent_err_text(traceback.format_exc()),
                e=e,
            )
            return {}

        if isinstance(to_save, dict):
            return to_save
        elif to_save is not None:
            self._adderr(
                "Unexpected return value '%s' from $ext save function", to_save
            )

        return {}

    def maybe_get_save_values_from_save_block(self, key, to_check):
        """Save a value from a specific block in the response

        This is different from maybe_get_save_values_from_ext - depends on the kind of response

        Args:
            to_check (dict): An element of the response from which the given key
                is extracted
            key (str): Key to use

        Returns:
            dict: dictionary of save_name: value, where save_name is the key we
                wanted to save this value as
        """
        saved = {}

        try:
            expected = self.expected["save"][key]
        except KeyError:
            logger.debug("Nothing expected to save for %s", key)
            return {}

        if not to_check:
            self._adderr("No %s in response (wanted to save %s)", key, expected)
        else:
            for save_as, joined_key in expected.items():
                try:
                    saved[save_as] = recurse_access_key(to_check, joined_key)
                except (
                    exceptions.InvalidQueryResultTypeError,
                    exceptions.KeySearchNotFoundError,
                ) as e:
                    self._adderr(
                        "Wanted to save '%s' from '%s', but it did not exist in the response",
                        joined_key,
                        key,
                        e=e,
                    )

        if saved:
            logger.debug("Saved %s for '%s' from response", saved, key)

        return saved
