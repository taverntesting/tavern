import logging
from typing import Any

from box.box import Box

from tavern._core import exceptions
from tavern._core.pytest import call_hook
from tavern._core.report import attach_yaml
from tavern._plugins.common.response import CommonResponse
from tavern._plugins.graphql.client import (
    GraphQLClient,
    GraphQLResponseLike,
    ResultOrErr,
)

logger: logging.Logger = logging.getLogger(__name__)


class GraphQLResponse(CommonResponse):
    """GraphQL response verification for HTTP and WS"""

    session: GraphQLClient

    def __init__(self, session, name: str, expected: dict, test_block_config):
        """Initialize GraphQL response validator.

        Args:
            session: GraphQL client instance
            name: Name of the test block
            expected: Expected response configuration
            test_block_config: Test block configuration
        """
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
        """Validate GraphQL response structure: data or errors top-level

        Checks if the response body contains valid GraphQL response structure
        with either 'data' or 'errors' keys at the top level.

        Args:
            body: Response body to validate
        """
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
        we wanted to save for use in future requests.

        Args:
            response: The GraphQL response to verify

        Returns:
            Dictionary of saved values from the response

        Raises:
            TestFailError: If verification fails with collected errors
        """

        graphql_responses = self.expected.get("graphql_responses", [])

        sync_responses_list: list[dict] = [
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
            try:
                to_save: dict = self.session._threaded_async_loop.run_coroutine(
                    self._handle_subscription_responses(sub_responses_list),
                    timeout=30.0,
                )
            except TimeoutError as e:
                self._adderr(f"Timed out waiting for subscription responses: {e}")
            else:
                saved.update(to_save)

        if self.errors:
            raise exceptions.TestFailError(
                f"Test '{self.name:s}' failed:\n{self._str_errors():s}",
                failures=self.errors,
            )

        return saved

    async def _handle_subscription_responses(
        self, sub_responses_list: list[dict]
    ) -> dict:
        """Handle subscription responses concurrently.

        Processes subscription-based GraphQL responses by waiting for messages
        on each subscription and validating them against expected responses.

        Args:
            sub_responses_list: List of subscription response configurations

        Returns:
            Dictionary of saved values from subscription responses
        """

        async def get_subscription_results(
            expected_resp,
        ) -> ResultOrErr | None:
            """Get subscription message result for an expected response.

            Waits for the next message on a subscription operation and returns
            the result.

            Args:
                expected_resp: Expected response configuration for subscription

            Returns:
                response or None if error occurred
            """
            op_name = expected_resp["subscription"]
            timeout: int | float = expected_resp.get("timeout", 3.0)
            try:
                response = await self.session.get_next_message(op_name, timeout)
            except TimeoutError:
                self._adderr(
                    f"Timed out waiting for subscription message on '{op_name}'"
                )
                return None
            except Exception as e:
                logger.exception(
                    f"Error getting subscription message on '{op_name}': {e}"
                )
                self._adderr(f"Error getting subscription message on '{op_name}': {e}")
                return None

            if response is None:
                self._adderr(f"Subscription message on '{op_name}' was None")
                return None

            return response

        saved = {}

        async def async_generator_wrapper():
            """Asynchronous generator that yields expected responses with results.

            For each expected subscription response, gets the subscription result
            and yields the pair for processing.

            Yields:
                Tuple of (expected_resp, response) for each subscription
            """
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
        expected_resp: dict,
        response: GraphQLResponseLike,
    ) -> dict[Any, Any]:
        """Check a synchronous GraphQL response against expected values.

        Validates a synchronous (non-subscription) GraphQL response by checking
        for expected errors and validating the response data.

        Args:
            expected_resp: Expected response configuration
            response: Actual GraphQL response to validate

        Returns:
            Dictionary of saved values from the response
        """
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
                found = False
                for got_error in got_error_messages:
                    if expected_error in got_error:
                        found = True

                if not found:
                    self._adderr(
                        f"error message '{expected_error}' not found in returned error messages (had {got_error_messages})"
                    )
        elif response.result.errors:
            self._adderr(
                f"got errors when none were expected: {response.result.errors}"
            )
            return {}

        body = response.result.data
        self._validate_block("data", body, read_from=expected_resp)  # type:ignore

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
