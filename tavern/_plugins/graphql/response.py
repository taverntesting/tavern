import logging
from typing import Any

import requests
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
        try:
            response_json = response.json()

            # Check for GraphQL-specific errors
            if "errors" in response_json:
                logger.warning(
                    "GraphQL errors in response: %s", response_json["errors"]
                )

            # Check for data field
            if "data" not in response_json and "errors" not in response_json:
                raise exceptions.BadSchemaError(
                    "GraphQL response must contain 'data' or 'errors' field"
                )

        except ValueError as e:
            raise exceptions.BadSchemaError(f"Invalid JSON response: {e}") from e

    def _verify_status_code(self, response: requests.Response):
        """Verify HTTP status code matches expected"""
        expected = self.expected["status_code"]
        actual = response.status_code

        if isinstance(expected, list):
            if actual not in expected:
                self._adderr("Status code %s not in expected list %s", actual, expected)
        elif actual != expected:
            self._adderr("Status code %s not equal to expected %s", actual, expected)

    def verify(self, response: requests.Response):
        """Verify GraphQL response against expected"""
        self.response = response

        # Basic HTTP status verification
        self._verify_status_code(response)

        # GraphQL-specific validation
        self._validate_response_format(response)

        # Standard response verification from base class
        return super().verify(response)
