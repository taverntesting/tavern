import json
import logging

from urllib.parse import urlparse, parse_qs

from requests.status_codes import _codes

from tavern.util.dict_util import recurse_access_key, deep_dict_merge
from tavern.util import exceptions
from tavern.util.exceptions import TestFailError
from tavern.response.base import BaseResponse, indent_err_text

logger = logging.getLogger(__name__)


class RestResponse(BaseResponse):
    def __init__(self, session, name, expected, test_block_config):
        # pylint: disable=unused-argument

        super(RestResponse, self).__init__()

        defaults = {"status_code": 200}

        self.name = name

        self._check_for_validate_functions(expected)

        self.expected = deep_dict_merge(defaults, expected)
        self.response = None
        self.test_block_config = test_block_config
        self.status_code = None

        def check_code(code):
            if code not in _codes:
                logger.warning("Unexpected status code '%s'", code)

        if isinstance(self.expected["status_code"], int):
            check_code(self.expected["status_code"])
        else:
            for code in self.expected["status_code"]:
                check_code(code)

    def __str__(self):
        if self.response:
            return self.response.text.strip()
        else:
            return "<Not run yet>"

    def _verbose_log_response(self, response):
        """Verbosely log the response object, with query params etc."""

        logger.info("Response: '%s'", response)

        def log_dict_block(block, name):
            if block:
                to_log = name + ":"

                if isinstance(block, list):
                    for v in block:
                        to_log += "\n  - {}".format(v)
                elif isinstance(block, dict):
                    for k, v in block.items():
                        to_log += "\n  {}: {}".format(k, v)
                else:
                    to_log += "\n {}".format(block)
                logger.debug(to_log)

        log_dict_block(response.headers, "Headers")

        try:
            log_dict_block(response.json(), "Body")
        except ValueError:
            pass

        redirect_query_params = self._get_redirect_query_params(response)
        if redirect_query_params:
            parsed_url = urlparse(response.headers["location"])
            to_path = "{0}://{1}{2}".format(*parsed_url)
            logger.debug("Redirect location: %s", to_path)
            log_dict_block(redirect_query_params, "Redirect URL query parameters")

    def _get_redirect_query_params(self, response):
        """If there was a redirect header, get any query parameters from it
        """

        try:
            redirect_url = response.headers["location"]
        except KeyError as e:
            if "redirect_query_params" in self.expected.get("save", {}):
                self._adderr(
                    "Wanted to save %s, but there was no redirect url in response",
                    self.expected["save"]["redirect_query_params"],
                    e=e,
                )
            redirect_query_params = {}
        else:
            parsed = urlparse(redirect_url)
            qp = parsed.query
            redirect_query_params = {i: j[0] for i, j in parse_qs(qp).items()}

        return redirect_query_params

    def _check_status_code(self, status_code, body):
        expected_code = self.expected["status_code"]

        if (isinstance(expected_code, int) and status_code == expected_code) or (
            isinstance(expected_code, list) and (status_code in expected_code)
        ):
            logger.debug(
                "Status code '%s' matched expected '%s'", status_code, expected_code
            )
            return
        else:
            if 400 <= status_code < 500:
                # special case if there was a bad request. This assumes that the
                # response would contain some kind of information as to why this
                # request was rejected.
                self._adderr(
                    "Status code was %s, expected %s:\n%s",
                    status_code,
                    expected_code,
                    indent_err_text(json.dumps(body)),
                )
            else:
                self._adderr(
                    "Status code was %s, expected %s", status_code, expected_code
                )

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
        self._verbose_log_response(response)

        self.response = response
        self.status_code = response.status_code

        # Get things to use from the response
        try:
            body = response.json()
        except ValueError:
            body = None

        redirect_query_params = self._get_redirect_query_params(response)

        # Run validation on response
        self._check_status_code(response.status_code, body)

        self._validate_block("body", body)
        self._validate_block("headers", response.headers)
        self._validate_block("redirect_query_params", redirect_query_params)

        self._maybe_run_validate_functions(response)

        # Get any keys to save
        saved = {}

        saved.update(self._save_value("body", body))
        saved.update(self._save_value("headers", response.headers))
        saved.update(self._save_value("redirect_query_params", redirect_query_params))

        saved.update(self.maybe_get_save_values_from_ext(response, self.expected))

        # Check cookies
        for cookie in self.expected.get("cookies", []):
            if cookie not in response.cookies:
                self._adderr("No cookie named '%s' in response", cookie)

        if self.errors:
            raise TestFailError(
                "Test '{:s}' failed:\n{:s}".format(self.name, self._str_errors()),
                failures=self.errors,
            )

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

        if blockname == "headers":
            # Special case for headers. These need to be checked in a case
            # insensitive manner
            block = {i.lower(): j for i, j in block.items()}
            expected_block = {i.lower(): j for i, j in expected_block.items()}

        logger.debug("Validating response %s against %s", blockname, expected_block)

        # 'strict' could be a list, in which case we only want to enable strict
        # key checking for that specific bit of the response
        test_strictness = self.test_block_config["strict"]
        if isinstance(test_strictness, list):
            block_strictness = blockname in test_strictness
        else:
            block_strictness = test_strictness

        self.recurse_check_key_match(expected_block, block, blockname, block_strictness)

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
