import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any, Optional, Union

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.exceptions import TransportQueryError
from gql.transport.websockets import WebsocketsTransport
from graphql import ExecutionResult

from tavern._plugins.common.response import ResponseLike

logger: logging.Logger = logging.getLogger(__name__)

_SubResponse = (
    AsyncGenerator[dict[str, Any], None] | AsyncGenerator[ExecutionResult, None]
)
"""The type of a response from a subscription."""

ResultOrErr = Union[ExecutionResult, TransportQueryError]
"""The type returned from a gql query"""


@dataclass(kw_only=True)
class GraphQLResponseLike(ResponseLike):
    """A response-like object implementing the ResponseLike protocol for GraphQL responses"""

    result: ResultOrErr
    headers: dict[str, str] = field(default_factory=dict)

    @property
    def text(self) -> str:
        """Return the JSON serialized representation of the GraphQL result data.

        Returns:
            A JSON string representation of the result data.
        """
        if not self.result:
            raise ValueError("No GraphQL result to return")
        return json.dumps(self.result.data)

    def json(self) -> Any:
        """Parse and return the JSON content of the response"""
        return self.result.data


class GraphQLClient:
    """GraphQL client for HTTP requests and subscriptions over WebSocket"""

    # separate clients for HTTP and WebSocket connections
    subscriptions: dict[str, _SubResponse]

    def __init__(self, **kwargs):
        """Initialize the GraphQL client."""
        self.default_headers = kwargs.get("headers", {})
        self.timeout = kwargs.get("timeout", 30)

        self.subscriptions = {}

        # Create a new event loop if one doesn't exist
        try:
            self._loop = asyncio.get_event_loop()
            # If the loop is already running we keep the existing loop;
            # otherwise we create a dedicated loop for sync usage.
            if not self._loop.is_running():
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)

        except RuntimeError:
            logger.debug("No event loop found, creating a new one", exc_info=True)
            # No event loop found, create a new one
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

    def __enter__(self):
        """Enter the context manager.

        Returns:
            The GraphQLClient instance.
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager and close WebSocket connections."""

        async def _close_subscriptions():
            """Close all active subscription generators."""
            await asyncio.gather(*(s.aclose() for s in self.subscriptions.values()))

        if self._loop.is_running():
            # If the event loop is already running, schedule cleanup as a task.
            self._loop.create_task(_close_subscriptions())
            return

        asyncio.run(_close_subscriptions())

    def make_request(
        self,
        url: str,
        query: str,
        variables: Optional[dict[str, Any]] = None,
        operation_name: Optional[str] = None,
        headers: Optional[dict] = None,
    ) -> ResponseLike:
        """Execute GraphQL query/mutation over HTTP using gql.

        Args:
            url: The GraphQL endpoint URL.
            query: The GraphQL query string.
            variables: Optional variables for the query.
            operation_name: Optional name of the operation to execute.
            headers: any headers to send with the request

        Returns:
            A GraphQLResponseLike object containing the query result.

        Raises:
            Exception: If the request fails or returns errors.
        """
        headers = headers or {}
        headers = dict(self.default_headers, **headers)
        headers["Content-Type"] = "application/json"

        transport = AIOHTTPTransport(
            url=url,
            headers=headers,
            timeout=self.timeout,
        )
        http_client = Client(transport=transport)

        query_gql = gql(query)
        query_gql.variable_values = variables or {}
        query_gql.operation_name = operation_name

        result: ExecutionResult = http_client.execute(
            query_gql,
            get_execution_result=True,
        )

        return GraphQLResponseLike(result=result)

    def start_subscription(
        self, url: str, query: str, variables: dict, operation_name: str
    ) -> None:
        """Start a GraphQL subscription over WS using gql WebSockets transport.

        Args:
            url: The GraphQL WebSocket endpoint URL.
            query: The GraphQL subscription query string.
            variables: Variables for the subscription query.
            operation_name: Name of the subscription operation.

        Raises:
            ValueError: If operation_name is not provided.
            Exception: If the subscription fails to start.
        """
        if operation_name is None:
            raise ValueError("operation_name required for subscriptions")

        if operation_name in self.subscriptions:
            raise ValueError(
                f"Subscription with name '{operation_name}' already exists"
            )

        # Prepare headers
        headers = dict(self.default_headers)

        # Create WebSocket transport
        ws_url = url.replace("http://", "ws://").replace("https://", "wss://")
        ws_transport = WebsocketsTransport(
            url=ws_url,
            headers=headers,
            connect_timeout=self.timeout,
        )

        # Create client with WebSocket transport
        ws_client = Client(transport=ws_transport)

        # Parse the GraphQL query
        query_gql = gql(query)
        query_gql.variable_values = variables or {}
        query_gql.operation_name = operation_name

        # Execute the subscription - this returns a generator
        try:
            # Using the subscription as a generator that yields results
            # Run the async subscription in the event loop
            async def _create_subscription():
                subscription_generator = ws_client.subscribe_async(query_gql)
                self.subscriptions[operation_name] = subscription_generator

            # Use the appropriate loop: if already running, schedule; else run directly.
            if self._loop.is_running():
                self._loop.create_task(_create_subscription())
            else:
                self._loop.run_until_complete(_create_subscription())

            logger.debug(f"Started subscription {operation_name}")
            # Return the generator to allow iterating through subscription messages
        except Exception as e:
            logger.error(f"Failed to start subscription: {e}")
            raise

    async def get_next_message(
        self, op_name: str, timeout: float = 5.0
    ) -> Optional[_SubResponse]:
        """Get next message from subscription generator.

        Args:
            op_name: The name of the subscription operation.
            timeout: Timeout in seconds to wait for the next message.

        Returns:
            The next message from the subscription, or None if the subscription
            ended.

        Raises:
            ValueError: If the subscription name is not found.
            TimeoutError: If the timeout is reached while waiting.
            Exception: If an error occurs while getting the next message.
        """
        if op_name not in self.subscriptions:
            raise ValueError(
                f"Subscription with name '{op_name}' not found (have: {self.subscriptions.keys()} )"
            )

        subscription_generator = self.subscriptions[op_name]

        # Get the next item from the async iterator
        try:
            return await asyncio.wait_for(
                anext(subscription_generator), timeout=timeout
            )
        except StopAsyncIteration:
            logger.error(
                f"got unexpected StopAsyncIteration from subscription {op_name}"
            )
            return None
        except TimeoutError as e:
            logger.error(f"Timeout getting next message from subscription: {e}")
            raise
        except Exception as e:
            logger.error(f"Error getting next message from subscription: {e}")
            raise
