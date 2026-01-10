import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any, Optional, Union

from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.exceptions import TransportQueryError, TransportServerError
from gql.transport.websockets import WebsocketsTransport
from graphql import ExecutionResult

from tavern._core.asyncio import ThreadedAsyncLoop
from tavern._plugins.common.response import ResponseLike

logger: logging.Logger = logging.getLogger(__name__)

_SubResponse = (
    AsyncGenerator[dict[str, Any], None] | AsyncGenerator[ExecutionResult, None]
)
"""The type of a response from a subscription."""

ResultOrErr = Union[ExecutionResult, TransportQueryError]
"""The type returned from a gql query"""


class ClientCacheKey:
    """Cache key for GraphQL clients.

    Uses a tuple of sorted header items to ensure hashability.
    """

    url: str
    headers: tuple[tuple[str, str], ...]
    timeout: int

    def __init__(self, url: str, headers: dict[str, str], timeout: int):
        """Initialize ClientCacheKey with conversion of headers dict to tuple.

        Args:
            url: The URL for the transport
            headers: Headers dictionary
            timeout: Timeout in seconds
        """
        # Convert headers dict to sorted tuple for hashability
        self.url = url
        self.headers = tuple(sorted(headers.items()))
        self.timeout = timeout

    def __hash__(self) -> int:
        """Make ClientCacheKey hashable."""
        return hash((self.url, self.headers, self.timeout))

    def __eq__(self, other: object) -> bool:
        """Compare two ClientCacheKey instances."""
        if not isinstance(other, ClientCacheKey):
            return NotImplemented
        return (
            self.url == other.url
            and self.headers == other.headers
            and self.timeout == other.timeout
        )

    def __repr__(self) -> str:
        """String representation of ClientCacheKey."""
        return f"ClientCacheKey(url={self.url!r}, headers={self.headers!r}, timeout={self.timeout})"


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

    _subscriptions: dict[str, _SubResponse]
    """Dictionary of active subscriptions, keyed by subscription name."""

    _to_close: list[AsyncGenerator]
    """List of subscription generators to close when the client is closed."""

    _gql_client_cache: dict[ClientCacheKey, Client]
    """Cache of GraphQL clients to avoid creating new ones for the same URL."""

    _transport_cache: dict[ClientCacheKey, AIOHTTPTransport]
    """Cache of HTTP transports associated with each client."""

    def __init__(self, **kwargs):
        """Initialize the GraphQL client."""
        self.default_headers = kwargs.get("headers", {})
        self.timeout = kwargs.get("timeout", 30)

        self._subscriptions = {}
        self._to_close = []
        self._gql_client_cache = {}
        self._transport_cache = {}

        self._threaded_async_loop = ThreadedAsyncLoop()

    def __enter__(self):
        """Enter the context manager.

        Returns:
            The GraphQLClient instance.
        """
        self._threaded_async_loop.__enter__()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit the context manager and close WebSocket connections."""

        async def _close_subscriptions():
            """Close all active subscription generators."""
            await asyncio.gather(*(s.aclose() for s in self._subscriptions.values()))
            await asyncio.gather(*(s.aclose() for s in self._to_close))
            await asyncio.gather(*(s.close() for s in self._transport_cache.values()))

        try:
            # Schedule the closing of subscriptions in the event loop and
            # wait for the closing operations to complete with a timeout
            self._threaded_async_loop.run_coroutine(_close_subscriptions(), timeout=5.0)
        except TimeoutError:
            logger.warning("Timed out waiting for subscriptions to close")

        # Join the thread with a timeout to prevent indefinite blocking
        self._threaded_async_loop.__exit__(exc_type, exc_val, exc_tb)

    def make_request(
        self,
        url: str,
        query: str,
        variables: Optional[dict[str, Any]] = None,
        operation_name: Optional[str] = None,
        headers: Optional[dict] = None,
        has_files: bool = False,
    ) -> ResponseLike:
        """Execute GraphQL query/mutation over HTTP using gql.

        Args:
            url: The GraphQL endpoint URL.
            query: The GraphQL query string.
            variables: Optional variables for the query.
            operation_name: Optional name of the operation to execute.
            headers: any headers to send with the request
            has_files: whether the request contains files

        Returns:
            A GraphQLResponseLike object containing the query result.

        Raises:
            Exception: If the request fails or returns errors.
        """
        headers = headers or {}
        headers = dict(self.default_headers, **headers)

        # Create a cache key for the client
        client_key = ClientCacheKey(
            url=url,
            headers=headers,
            timeout=self.timeout,
        )

        # Get or create the GraphQL client
        http_client = self._gql_client_cache.get(client_key)
        if http_client is None:
            transport = AIOHTTPTransport(
                url=url,
                headers=headers,
                timeout=self.timeout,
            )
            http_client = Client(transport=transport)
            self._gql_client_cache[client_key] = http_client
            self._transport_cache[client_key] = transport
            logger.debug(f"Created new GraphQL client for {url}")
        else:
            logger.debug(f"Reusing cached GraphQL client for {url}")

        query_gql = gql(query)
        query_gql.variable_values = variables or {}
        query_gql.operation_name = operation_name

        try:
            result: ExecutionResult = http_client.execute(
                query_gql,
                get_execution_result=True,
                upload_files=has_files,
            )
        except (TransportQueryError, TransportServerError) as e:
            logger.debug(f"GraphQL request failed: {e}", exc_info=True)
            raise

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

        if operation_name in self._subscriptions:
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

            async def subscribe_async_wrapper() -> AsyncGenerator:
                """Wrapper for subscribe_async because that method does not close subscriptions properly."""
                async with ws_client as session:
                    generator = session.subscribe(query_gql)

                    self._to_close.append(generator)

                    async for result in generator:
                        yield result

            # Using the subscription as a generator that yields results
            # Run the async subscription in the event loop
            async def _create_subscription():
                self._subscriptions[operation_name] = subscribe_async_wrapper()

            self._threaded_async_loop.run_coroutine(
                _create_subscription(),
                timeout=5.0,
            )

            logger.debug(f"Started subscription {operation_name}")
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
        if op_name not in self._subscriptions:
            raise ValueError(
                f"Subscription with name '{op_name}' not found (have: {self._subscriptions.keys()} )"
            )

        subscription_generator = self._subscriptions[op_name]

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
