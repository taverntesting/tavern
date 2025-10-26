import json
import logging
from typing import Any, Union

import requests

from tavern._core.pytest.config import TestConfig
from tavern._core.report import attach_yaml
from tavern._plugins.common.response import CommonResponse
from tavern.response import indent_err_text

logger: logging.Logger = logging.getLogger(__name__)


class GraphQLResponse(CommonResponse):
    """GraphQL response verification"""

    def __init__(
        self,
        session,
        name: str,
        expected: dict[str, Any],
        test_block_config: TestConfig,
    ) -> None:
        # GraphQL responses should always have status code 200
        super().__init__(
            session, name, expected, test_block_config, default_status_code=200
        )

    def _check_status_code(self, status_code: Union[int, list[int]], body: Any) -> None:
        """Check GraphQL status code (should always be 200)"""
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
            self._adderr(
                f"Response contains invalid top-level keys: {invalid_keys}. Only 'data' and 'errors' are allowed."
            )

        # Check mutual exclusivity - should have either 'data' or 'errors', but can have both in some cases
        has_data = "data" in body
        has_errors = "errors" in body

        if not has_data and not has_errors:
            self._adderr(
                "Response must contain either 'data' or 'errors' at the top level"
            )

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
        body, redirect_query_params = self._common_verify_setup(response)

        # Run validation on response
        self._check_status_code(response.status_code, body)

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
        saved = self._common_verify_save(body, response, redirect_query_params)

        self._common_verify_finalize()

        return saved
