import json
import logging
from typing import Any, Union

import requests

from tavern._core import exceptions
from tavern._core.pytest import call_hook
from tavern._core.report import attach_yaml
from tavern._plugins.common.response import CommonResponse
from tavern.response import indent_err_text

logger: logging.Logger = logging.getLogger(__name__)


class GraphQLResponse(CommonResponse):
    """GraphQL response verification"""

    def _check_status_code(self, status_code: int, body: Any) -> None:
        """Check GraphQL status code (should always be 200)"""
        if int(status_code) == 200:
            logger.debug("Status code '%s' matched expected '%s'", status_code, 200)
            return
        else:
            # For GraphQL, non-200 status codes are always an error
            self._adderr(
                "Status code was %s, expected %s:\n%s",
                status_code,
                200,
                indent_err_text(json.dumps(body) if body else "<no body>"),
            )

    def _validate_graphql_response_structure(self, body: Any) -> None:
        """Validate that GraphQL response has proper structure with only 'data' or 'errors' at top level"""
        if body is None:
            self._adderr("Response body is empty or not valid JSON")
            return

        if not isinstance(body, dict):
            self._adderr("Response body is not a JSON object (got %s)", body)
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

        call_hook(
            self.test_block_config,
            "pytest_tavern_beta_after_every_response",
            expected=self.expected,
            response=response,
        )

        body = self._common_verify_setup(response)

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
        saved = self._common_verify_save(body, response)

        if self.errors:
            raise exceptions.TestFailError(
                f"Test '{self.name:s}' failed:\n{self._str_errors():s}",
                failures=self.errors,
            )

        return saved
