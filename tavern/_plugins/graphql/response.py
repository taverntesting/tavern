import logging
from typing import Any

import requests
from _core.pytest import call_hook
from requests.status_codes import _codes  # type:ignore

from tavern._core import exceptions
from tavern._core.dict_util import deep_dict_merge
from tavern._core.pytest.config import TestConfig
from tavern.response import BaseResponse

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

    def _validate_response_format(self, response: requests.Response):
        """Validate GraphQL response structure"""

        call_hook(
            self.test_block_config,
            "pytest_tavern_beta_after_every_response",
            expected=self.expected,
            response=response,
        )

        # Handle mock subscription responses
        try:
            body = response.json()
        except ValueError:
            self._adderr("Response is not valid JSON")
        else:
            response_json = response.json()

            # Skip validation for mock subscription responses
            if response_json.get("subscription") == "established":
                self._adderr("Did not expect a subscription response")

            if "errors" in response_json and "errors" not in self.expected:
                assert 0
                # TODO: deserialise errors to list, add each as an error with self._adderr

            if "data" in response_json:
                if "errors" in self.expected:
                    self._adderr(
                        "Expected 'errors' field in response, but found 'data'"
                    )

                self._validate_block("json", body)

            self._maybe_run_validate_functions(response)

        if self.errors:
            raise exceptions.TestFailError(
                f"Test '{self.name:s}' failed:\n{self._str_errors():s}",
                failures=self.errors,
            )

    def _verify_status_code(self, response: requests.Response):
        """Verify HTTP status code matches expected"""
        # For mock subscription responses, skip status code verification
        actual = response.status_code

        expected = self.expected["status_code"]
        if isinstance(expected, list):
            if actual not in expected:
                self._adderr("Status code %s not in expected list %s", actual, expected)
        elif actual != expected:
            self._adderr("Status code %s not equal to expected %s", actual, expected)

    def verify(self, response: requests.Response | Any):
        """Verify GraphQL response against expected"""
        self.response = response

        # Basic HTTP status verification (skipped for subscriptions)
        self._verify_status_code(response)

        # GraphQL-specific validation
        self._validate_response_format(response)

        # Additional verification for subscriptions
        # TODO
        # self._verify_subscription_messages(response)

        return {}
