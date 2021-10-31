import json
import logging
from urllib.parse import parse_qs, urlparse

from requests.status_codes import _codes  # type:ignore

from tavern.response.base import BaseResponse, indent_err_text
from tavern.testutils.pytesthook.newhooks import call_hook
from tavern.util import exceptions
from tavern.util.dict_util import deep_dict_merge
from tavern.util.report import attach_yaml

logger = logging.getLogger(__name__)


class RestResponse(BaseResponse):
    def __init__(self, session, name, expected, test_block_config):
        # pylint: disable=unused-argument

        defaults = {"status_code": 200}

        super().__init__(name, deep_dict_merge(defaults, expected), test_block_config)

        self.status_code = None

        def check_code(code):
            if int(code) not in _codes:
                logger.warning("Unexpected status code '%s'", code)

        in_file = self.expected["status_code"]
        try:
            if isinstance(in_file, list):
                for code_ in in_file:
                    check_code(code_)
            else:
                check_code(in_file)
        except TypeError as e:
            raise exceptions.BadSchemaError("Invalid code") from e

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
        """If there was a redirect header, get any query parameters from it"""

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

        call_hook(
            self.test_block_config,
            "pytest_tavern_beta_after_every_response",
            expected=self.expected,
            response=response,
        )

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

        self._validate_block("json", body)
        self._validate_block("headers", response.headers)
        self._validate_block("redirect_query_params", redirect_query_params)

        attach_yaml(
            {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": body,
                "redirect_query_params": redirect_query_params,
            },
            name="rest_response",
        )

        self._maybe_run_validate_functions(response)

        # Get any keys to save
        saved = {}

        saved.update(self.maybe_get_save_values_from_save_block("json", body))
        saved.update(
            self.maybe_get_save_values_from_save_block("headers", response.headers)
        )
        saved.update(
            self.maybe_get_save_values_from_save_block(
                "redirect_query_params", redirect_query_params
            )
        )

        saved.update(self.maybe_get_save_values_from_ext(response, self.expected))

        # Check cookies
        for cookie in self.expected.get("cookies", []):
            if cookie not in response.cookies:
                self._adderr("No cookie named '%s' in response", cookie)

        if self.errors:
            raise exceptions.TestFailError(
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
            expected_block = self.expected[blockname]
        except KeyError:
            expected_block = None

        if isinstance(expected_block, dict):
            if expected_block.pop("$ext", None):
                raise exceptions.InvalidExtBlockException(
                    blockname,
                )

        if blockname == "headers" and expected_block is not None:
            # Special case for headers. These need to be checked in a case
            # insensitive manner
            block = {i.lower(): j for i, j in block.items()}
            expected_block = {i.lower(): j for i, j in expected_block.items()}

        logger.debug("Validating response %s against %s", blockname, expected_block)

        test_strictness = self.test_block_config["strict"]
        block_strictness = test_strictness.setting_for(blockname)
        self.recurse_check_key_match(expected_block, block, blockname, block_strictness)
