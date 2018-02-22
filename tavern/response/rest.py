import json
import traceback
import logging
import copy

try:
    from urllib.parse import urlparse, parse_qs
except ImportError:
    from urlparse import urlparse, parse_qs

from tavern.schemas.extensions import get_wrapped_response_function
from tavern.util.dict_util import recurse_access_key, deep_dict_merge
from tavern.util.exceptions import TestFailError
from .base import BaseResponse, indent_err_text

logger = logging.getLogger(__name__)


class RestResponse(BaseResponse):

    def __init__(self, session, name, expected, test_block_config):
        # pylint: disable=unused-argument

        super(RestResponse, self).__init__()

        defaults = {
            'status_code': 200
        }

        self.name = name
        body = expected.get("body") or {}

        if "$ext" in body:
            self.validate_function = get_wrapped_response_function(body["$ext"])
        else:
            self.validate_function = None

        self.expected = deep_dict_merge(defaults, expected)
        self.response = None
        self.test_block_config = test_block_config
        self.status_code = None

    def __str__(self):
        if self.response:
            return self.response.text.strip()
        else:
            return "<Not run yet>"

    def verify(self, response):
        """Verify response against expected values and returns any values that
        we wanted to save for use in future requests

        There are various ways to 'validate' a block - a specific function, just
        matching values, validating a schema, etc...

        Args:
            response (requests.Response): response object

        Returns:
            dict: Any saved values

        Raises:
            TestFailError: Something went wrong with validating the response
        """
        # pylint: disable=too-many-statements

        logger.info("Response: '%s' (%s)", response, response.content.decode("utf8"))

        self.response = response
        self.status_code = response.status_code

        try:
            body = response.json()
        except ValueError:
            body = None

        if response.status_code != self.expected["status_code"]:
            if 400 <= response.status_code < 500:
                self._adderr("Status code was %s, expected %s:\n%s",
                    response.status_code, self.expected["status_code"],
                    indent_err_text(json.dumps(body)),
                    )
            else:
                self._adderr("Status code was %s, expected %s",
                    response.status_code, self.expected["status_code"])

        if self.validate_function:
            try:
                self.validate_function(response)
            except Exception as e: #pylint: disable=broad-except
                self._adderr("Error calling validate function '%s':\n%s",
                    self.validate_function.func,
                    indent_err_text(traceback.format_exc()),
                    e=e)

        # Get any keys to save
        saved = {}

        try:
            redirect_url = response.headers["location"]
        except KeyError as e:
            if "redirect_query_params" in self.expected.get("save", {}):
                self._adderr("Wanted to save %s, but there was no redirect url in response",
                    self.expected["save"]["redirect_query_params"], e=e)
            qp_as_dict = {}
        else:
            parsed = urlparse(redirect_url)
            qp = parsed.query
            qp_as_dict = {i:j[0] for i, j in parse_qs(qp).items()}

        saved.update(self._save_value("body", body))
        saved.update(self._save_value("headers", response.headers))
        saved.update(self._save_value("redirect_query_params", qp_as_dict))

        for cookie in self.expected.get("cookies", []):
            if cookie not in response.cookies:
                self._adderr("No cookie named '%s' in response", cookie)

        try:
            wrapped = get_wrapped_response_function(self.expected["save"]["$ext"])
        except KeyError:
            logger.debug("No save function")
        else:
            try:
                to_save = wrapped(response)
            except Exception as e: #pylint: disable=broad-except
                self._adderr("Error calling save function '%s':\n%s",
                    wrapped.func,
                    indent_err_text(traceback.format_exc()),
                    e=e)
            else:
                if isinstance(to_save, dict):
                    saved.update(to_save)
                elif not isinstance(to_save, None):
                    self._adderr("Unexpected return value '%s' from $ext save function")

        self._validate_block("body", body)
        self._validate_block("headers", response.headers)
        self._validate_block("redirect_query_params", qp_as_dict)

        if self.errors:
            raise TestFailError("Test '{:s}' failed:\n{:s}".format(self.name, self._str_errors()))

        return saved

    def _validate_block(self, blockname, block):
        """Validate a block of the response

        Args:
            blockname (str): which part of the response is being checked
            block (dict): The actual part being checked
        """
        try:
            expected_block = self.expected[blockname] or {}
        except KeyError:
            expected_block = {}

        if isinstance(expected_block, dict):
            special = ["$ext"]
            # This has to be a dict at the moment - might be possible at some
            # point in future to allow a list of multiple ext functions as well
            # but would require some changes in init. Probably need to abtract
            # out the 'checking' a bit more.
            for s in special:
                try:
                    expected_block.pop(s)
                except KeyError:
                    pass

        logger.debug("Validating %s for %s", blockname, expected_block)

        self.recurse_check_key_match(expected_block, block, blockname)

    def _save_value(self, key, to_check):
        """Save a value in the response for use in future tests

        Args:
            to_check (dict): An element of the response from which the given key
                is extracted
            key (str): Key to use

        Returns:
            dict: dictionary of save_name: value, where save_name is the key we
                wanted to save this value as
        """
        espec = self.expected
        saved = {}

        try:
            expected = espec["save"][key]
        except KeyError:
            logger.debug("Nothing expected to save for %s", key)
            return {}

        if not to_check:
            self._adderr("No %s in response (wanted to save %s)",
                key, expected)
        else:
            for save_as, joined_key in expected.items():
                split_key = joined_key.split(".")
                try:
                    saved[save_as] = recurse_access_key(to_check, copy.copy(split_key))
                except (IndexError, KeyError) as e:
                    self._adderr("Wanted to save '%s' from '%s', but it did not exist in the response",
                        joined_key, key, e=e)

        if saved:
            logger.debug("Saved %s for '%s' from response", saved, key)

        return saved
