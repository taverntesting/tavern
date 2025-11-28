import logging
from typing import Any

from tavern._core import exceptions
from tavern._core.pytest import call_hook
from tavern._core.report import attach_yaml
from tavern._plugins.common.response import CommonResponse

logger: logging.Logger = logging.getLogger(__name__)


class GraphQLResponse(CommonResponse):
    """GraphQL response verification for HTTP and WS"""

    def __init__(self, session, name: str, expected: dict, test_block_config):
        self.session = session
        super().__init__(session, name, expected, test_block_config)

    def _validate_graphql_response_structure(self, body: Any) -> None:
        """Validate GraphQL response structure: data or errors top-level"""
        if body is None:
            self._adderr("GraphQL response body missing")
            return
        if not isinstance(body, dict):
            self._adderr("GraphQL body not dict: %r", body)
            return

        allowed = {"data", "errors"}
        if not allowed & set(body):
            self._adderr(
                "Response must contain either 'data' or 'errors' at the top level"
            )
        if set(body) - allowed:
            self._adderr(
                "Invalid GraphQL top-level keys: %s. Only 'data' and 'errors' are allowed",
                set(body) - allowed,
            )

    def verify(self, response: Any) -> dict:
        """Verify response against expected values and returns any values that
        we wanted to save for use in future requests"""

        graphql_responses = self.expected.get("graphql_responses", [])

        saved = {}

        for expected_resp in graphql_responses:
            call_hook(
                self.test_block_config,
                "pytest_tavern_beta_after_every_response",
                expected=expected_resp,
                response=response,
            )

            if "subscription" in expected_resp:
                op_name = expected_resp["subscription"]
                timeout: int | float = expected_resp.get("timeout", 5.0)
                ws_msg = self.session.get_next_message(op_name, timeout)
                if ws_msg is None:
                    self._adderr(
                        f"Timeout waiting for subscription message on '{op_name}' within {timeout}s"
                    )
                    continue

                body = ws_msg
                if "json" in expected_resp:
                    self._validate_block("json", body)

                attach_yaml(
                    {"ws_op": op_name, "body": body},
                    name="graphql_ws_response",
                )
            else:
                # Regular HTTP GraphQL response
                body = (
                    self._common_verify_setup(response)
                    if hasattr(response, "_common_verify_setup")
                    else response.json()
                    if hasattr(response, "json")
                    else None
                )
                expected_status = expected_resp.get("status_code", 200)
                actual_status = getattr(response, "status_code", 200)
                if actual_status != expected_status:
                    self._adderr(
                        f"Status code was {actual_status}, expected {expected_status}"
                    )
                self._validate_graphql_response_structure(body)
                self._validate_block("json", body)  # type:ignore
                self._validate_block("headers", getattr(response, "headers", {}))

                attach_yaml(
                    {
                        "status_code": actual_status,
                        "headers": dict(getattr(response, "headers", {})),
                        "body": body,
                    },
                    name="graphql_response",
                )
                saved.update(self._common_verify_save(body, response))

            self._maybe_run_validate_functions(
                response if "subscription" not in expected_resp else ws_msg
            )

        if self.errors:
            raise exceptions.TestFailError(
                f"Test '{self.name:s}' failed:\n{self._str_errors():s}",
                failures=self.errors,
            )

        return saved
