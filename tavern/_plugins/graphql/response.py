import contextlib
import json
import logging
from collections.abc import Mapping
from typing import Any

import requests
from requests.status_codes import _codes  # type:ignore

from tavern._core import exceptions
from tavern._core.dict_util import deep_dict_merge
from tavern._core.pytest.config import TestConfig
from tavern._core.pytest.newhooks import call_hook
from tavern._core.report import attach_yaml
from tavern.response import BaseResponse, indent_err_text

logger: logging.Logger = logging.getLogger(__name__)


class GraphQLResponse(BaseResponse):
    """GraphQL response verification"""

    def __init__(
        self,
        session,
        name: str,
        expected: dict[str, Any],
        test_block_config: TestConfig,
    ) -> None:
        # GraphQL responses should always have status code 200
        defaults = {"status_code": 200}

        super().__init__(name, deep_dict_merge(defaults, expected), test_block_config)

        def check_code(code: int) -> None:
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

    def __str__(self) -> str:
        if self.response:
            return self.response.text.strip()
        else:
            return "<Not run yet>"

    def _verbose_log_response(self, response: requests.Response) -> None:
        """Verbosely log the response object, with query params etc."""

        logger.info("Response: '%s'", response)

        def log_dict_block(block, name):
            if block:
                to_log = name + ":"

                if isinstance(block, list):
                    for v in block:
                        to_log += f"\n  - {v}"
                elif isinstance(block, dict):
                    for k, v in block.items():
                        to_log += f"\n  {k}: {v}"
                else:
                    to_log += f"\n {block}"
                logger.debug(to_log)

        log_dict_block(response.headers, "Headers")

        with contextlib.suppress(ValueError):
            log_dict_block(response.json(), "Body")

    def _check_status_code(self, response: requests.Response, body: Any) -> None:
        """Check GraphQL status code (should always be 200)"""
        status_code = response.status_code
        expected_code = self.expected["status_code"]

        if (isinstance(expected_code, int) and status_code == expected_code) or (
            isinstance(expected_code, list) and (status_code in expected_code)
        ):
            logger.debug(
                "Status code '%s' matched expected '%s'", status_code, expected_code
            )
            return
        else:
            # For GraphQL, non-200 status codes are always an error
            self._adderr(
                "Status code was %s, expected %s:\n%s",
                status_code,
                expected_code,
                indent_err_text(json.dumps(body) if body else "<no body>"),
            )

    def _validate_graphql_response_structure(self, body: Any) -> None:
        """Validate that GraphQL response has proper structure with only 'data' or 'errors' at top level"""
        if body is None:
            self._adderr("Response body is empty or not valid JSON")
            return

        if not isinstance(body, dict):
            self._adderr("Response body is not a JSON object")
            return

        # Check that response has only 'data' or 'errors' at the top level
        allowed_keys = {"data", "errors"}
        actual_keys = set(body.keys())

        invalid_keys = actual_keys - allowed_keys
        if invalid_keys:
            self._adderr(f"Response contains invalid top-level keys: {invalid_keys}. Only 'data' and 'errors' are allowed.")

        # Check mutual exclusivity - should have either 'data' or 'errors', but can have both in some cases
        has_data = "data" in body
        has_errors = "errors" in body

        if not has_data and not has_errors:
            self._adderr("Response must contain either 'data' or 'errors' at the top level")

    def verify(self, response: requests.Response) -> dict:
        """Verify response against expected values and returns any values that
        we wanted to save for use in future requests

        Args:
            response: response object

        Returns:
            Any saved values

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

        # Get things to use from the response
        try:
            body = response.json()
        except ValueError:
            body = None

        # Run validation on response
        self._check_status_code(response, body)

        # Validate GraphQL-specific response structure
        self._validate_graphql_response_structure(body)

        # Validate other blocks (json, headers, etc.) with GraphQL-specific constraints
        if body is not None:
            self._validate_block("json", body)
        self._validate_block("headers", response.headers)

        attach_yaml(
            {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "body": body,
            },
            name="graphql_response",
        )

        self._maybe_run_validate_functions(response)

        # Get any keys to save
        saved: dict = {}

        if body is not None:
            saved.update(self.maybe_get_save_values_from_save_block("json", body))
        saved.update(
            self.maybe_get_save_values_from_save_block("headers", response.headers)
        )

        saved.update(self.maybe_get_save_values_from_ext(response, self.expected))

        if self.errors:
            raise exceptions.TestFailError(
                f"Test '{self.name:s}' failed:\n{self._str_errors():s}",
                failures=self.errors,
            )

        return saved

    def _validate_block(self, blockname: str, block: Mapping) -> None:
        """Validate a block of the response

        Args:
            blockname: which part of the response is being checked
            block: The actual part being checked
        """
        try:
            expected_block = self.expected[blockname]
        except KeyError:
            expected_block = None

        if isinstance(expected_block, dict):
            if expected_block.pop("$ext", None):
                raise exceptions.MisplacedExtBlockException(
                    blockname,
                )

        if blockname == "headers" and expected_block is not None:
            # Special case for headers. These need to be checked in a case
            # insensitive manner
            block = {i.lower(): j for i, j in block.items()}
            expected_block = {i.lower(): j for i, j in expected_block.items()}

        logger.debug("Validating response %s against %s", blockname, expected_block)

        test_strictness = self.test_block_config.strict
        block_strictness = test_strictness.option_for(blockname)
        self.recurse_check_key_match(expected_block, block, blockname, block_strictness)
