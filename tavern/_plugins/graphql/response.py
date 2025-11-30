import logging
from typing import Any

from box.box import Box

from tavern._core import exceptions
from tavern._core.pytest import call_hook
from tavern._core.report import attach_yaml
from tavern._plugins.common.response import CommonResponse
from tavern._plugins.graphql.client import GraphQLResponseLike, GraphQLClient

logger: logging.Logger = logging.getLogger(__name__)


class GraphQLResponse(CommonResponse):
    """GraphQL response verification for HTTP and WS"""

    session: GraphQLClient

    def __init__(self, session, name: str, expected: dict, test_block_config):
        self.session = session

        sync_responses = 0
        for resp in expected.get("graphql_responses", []):
            if resp.get("subscription") is None:
                sync_responses += 1

        if sync_responses > 1:
            raise exceptions.BadSchemaError(
                "Only one graphql_response can be synchronous"
            )

        expected["save"] = expected.get("save", {})
        for e in expected.get("graphql_responses", []):
            save_block: dict
            if save_block := e.get("save", {}):
                if not isinstance(save_block, dict):
                    raise exceptions.BadSchemaError(
                        "save block for graphql_response must be a dict"
                    )

                for to_save in save_block:
                    if to_save in expected["save"]:
                        raise exceptions.BadSchemaError(
                            f"save block for graphql_response cannot contain duplicate keys: {to_save}"
                        )

                expected["save"].update(save_block)

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

    def verify(self, response: GraphQLResponseLike) -> dict:
        """Verify response against expected values and returns any values that
        we wanted to save for use in future requests"""

        graphql_responses = self.expected.get("graphql_responses", [])

        sync_responses_list = [
            resp for resp in graphql_responses if "subscription" not in resp
        ]

        # Process synchronous responses (will actually be length 1)
        saved = {}
        for expected_resp in sync_responses_list:
            saved.update(self._check_sync_response(expected_resp, response))

        sub_responses_list = [
            resp for resp in graphql_responses if "subscription" in resp
        ]
        # Process subscription responses
        if sub_responses_list:
            saved.update(
                self.session._loop.run_until_complete(
                    self._handle_subscription_responses(sub_responses_list)
                )
            )

        if self.errors:
            raise exceptions.TestFailError(
                f"Test '{self.name:s}' failed:\n{self._str_errors():s}",
                failures=self.errors,
            )

        return saved

    async def _handle_subscription_responses(
        self, sub_responses_list: list[dict]
    ) -> dict:
        """Handle subscription responses concurrently"""

        async def get_subscription_results(expected_resp) -> tuple[dict, dict] | None:
            op_name = expected_resp["subscription"]
            timeout: int | float = expected_resp.get("timeout", 5.0)
            try:
                response = await self.session.get_next_message(op_name, timeout)
            except TimeoutError:
                self._adderr(
                    f"Timed out waiting for subscription message on '{op_name}'"
                )
                return None
            except Exception:
                self._adderr(f"Error getting subscription message on '{op_name}'")
                return None

            if response is None:
                self._adderr(f"Subscription message on '{op_name}' was None")
                return None

            return expected_resp, response

        saved = {}

        async def async_generator_wrapper():
            for resp in sub_responses_list:
                yield resp, await get_subscription_results(resp)

        # Process the results using async for
        async for expected_resp, response in async_generator_wrapper():
            if response is None:
                continue
            op_name = expected_resp["subscription"]
            # Process successful subscription response
            body = response
            if "json" in expected_resp:
                self._validate_block("json", body)

            attach_yaml(
                {"ws_op": op_name, "body": body},
                name="graphql_ws_response",
            )

            call_hook(
                self.test_block_config,
                "pytest_tavern_beta_after_every_response",
                expected=expected_resp,
                response=response,
            )
            self._maybe_run_validate_functions(response)

            saved.update(self._common_verify_save(body, response))
            saved.update(
                self.maybe_get_save_values_from_save_block("data", {"data": body})
            )

        return saved

    def _check_sync_response(
        self,
        expected_resp,
        response: GraphQLResponseLike,
    ) -> dict[Any, Any]:
        call_hook(
            self.test_block_config,
            "pytest_tavern_beta_after_every_response",
            expected=expected_resp,
            response=response,
        )

        # Regular HTTP GraphQL response
        logger.info(f"response: {response}")

        expected_errors: list[str]
        if expected_errors := expected_resp.get("errors", []):
            if not response.result.errors:
                self._adderr("Expected errors but got none")
                return {}

            if len(expected_errors) != len(response.result.errors):
                self._adderr(
                    f"Expected {len(expected_errors)} errors but got {len(response.result.errors)}"
                )
                # Continue and do a best effort check

            got_error_messages = [
                Box(error).message for error in response.result.errors
            ]
            expected_errors = [Box(error).message for error in expected_errors]
            for expected_error in expected_errors:
                if expected_error not in got_error_messages:
                    self._adderr(
                        f"error message {expected_error} not found in returned error messages"
                    )
        elif response.result.errors:
            self._adderr(
                f"got errors when none were expected: {response.result.errors}"
            )
            return {}

        body = response.result.data
        self._validate_block("data", body)  # type:ignore

        attach_yaml(
            {
                "body": body,
            },
            name="graphql_response",
        )

        self._maybe_run_validate_functions(response)

        saved = {}
        saved.update(self._common_verify_save(body, response))
        saved.update(self.maybe_get_save_values_from_save_block("data", {"data": body}))

        return saved
