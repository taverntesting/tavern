import asyncio
import json
import logging
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from typing import Any, Optional

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

_ResultOrErr = ExecutionResult | TransportQueryError


@dataclass(kw_only=True)
class GraphQLResponseLike(ResponseLike):
    """A response-like object implementing the ResponseLike protocol for GraphQL responses"""

    result: _ResultOrErr
    headers: dict[str, str] = field(default_factory=dict)

    _json: Any = field(default=None, init=False)

    @property
    def text(self) -> str:
        return json.dumps(self.result.data)

    def json(self) -> Any:
        """Parse and return the JSON content of the response"""
        if self._json is None:
            try:
                self._json = json.loads(self.text)
            except ValueError as e:
                raise ValueError(
                    f"Response content is not valid JSON: {self.text}"
                ) from e
        return self._json


class GraphQLClient:
    """GraphQL client for HTTP requests and subscriptions over WebSocket"""

    # separate clients for HTTP and WebSocket connections
    http_client: Client | None = None
    ws_client: Client | None = None
    ws_transport: WebsocketsTransport | None = None

    subscriptions: dict[str, _SubResponse]

    def __init__(self, **kwargs):
        self.default_headers = kwargs.get("headers", {})
        self.timeout = kwargs.get("timeout", 30)

        self.subscriptions = {}

        # Create a new event loop if one doesn't exist
        try:
            self._loop = asyncio.get_event_loop()
            # Check if the loop is running - if not, we need to handle this differently
            if not self._loop.is_running():
                # Create a new loop for handling async operations in sync context
                self._loop = asyncio.new_event_loop()
                asyncio.set_event_loop(self._loop)
        except RuntimeError:
            # No event loop found, create a new one
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._close_ws()

    def update_session(self, **kwargs):
        """Update session with new configuration"""
        if "headers" in kwargs:
            self.default_headers.update(kwargs["headers"])

    def make_request(
        self,
        url: str,
        query: str,
        variables: Optional[dict[str, Any]] = None,
        operation_name: Optional[str] = None,
        method: str = "POST",
    ) -> ResponseLike:
        """Execute GraphQL query/mutation over HTTP using gql"""
        if method.upper() == "GET":
            raise NotImplementedError(
                "GET method not supported with gql transport. Use POST."
            )

        headers = dict(self.default_headers)
        headers["Content-Type"] = "application/json"

        transport = AIOHTTPTransport(
            url=url,
            headers=headers,
            timeout=self.timeout,
        )
        self.http_client = Client(transport=transport)

        query_gql = gql(query)

        result: ExecutionResult = self.http_client.execute(
            query_gql,
            variable_values=variables or {},
            operation_name=operation_name,
            get_execution_result=True,
        )

        return GraphQLResponseLike(result=result)

    def start_subscription(
        self, url: str, query: str, variables: dict, operation_name: str
    ) -> None:
        """Start a GraphQL subscription over WS using gql WebSockets transport"""
        if operation_name is None:
            raise ValueError("operation_name required for subscriptions")

        # Prepare headers
        headers = dict(self.default_headers)

        # Create WebSocket transport
        ws_url = url.replace("http://", "ws://").replace("https://", "wss://")
        self.ws_transport = WebsocketsTransport(
            url=ws_url,
            headers=headers,
            connect_timeout=self.timeout,
        )

        # Create client with WebSocket transport
        self.ws_client = Client(transport=self.ws_transport)

        # Parse the GraphQL query
        query_gql = gql(query)

        # Execute the subscription - this returns a generator
        try:
            # Using the subscription as a generator that yields results
            # Run the async subscription in the event loop
            async def _create_subscription():
                subscription_generator = self.ws_client.subscribe_async(
                    query_gql,
                    variable_values=variables or {},
                    operation_name=operation_name,
                )

                self.subscriptions[operation_name] = subscription_generator

            self._loop.run_until_complete(_create_subscription())

            logger.debug(f"Started subscription {operation_name}")
            # Return the generator to allow iterating through subscription messages
        except Exception as exc:
            logger.error(f"Failed to start subscription: {exc}")
            raise

    def get_next_message(self, op_name: str, timeout: float = 5.0) -> Optional[dict]:
        """
        Get next message from subscription generator.
        """
        if op_name not in self.subscriptions:
            raise ValueError(
                f"Subscription with name '{op_name}' not found (have: {self.subscriptions.keys()} )"
            )

        subscription_generator = self.subscriptions[op_name]

        async def _get_next():
            # Get the next item from the async iterator
            try:
                return await asyncio.wait_for(
                    subscription_generator.__anext__(), timeout=timeout
                )
            except StopAsyncIteration:
                return None

        try:
            message = self._loop.run_until_complete(_get_next())
            return message
        except TimeoutError as e:
            logger.error(f"Timeout getting next message from subscription: {e}")
            raise
        except Exception as e:
            logger.error(f"Error getting next message from subscription: {e}")
            raise

    def _close_ws(self):
        """Close WS connection"""
        if self.ws_client:
            try:
                self._loop.call_soon(self.ws_transport.close)
                logger.debug("WS connection closed")
            except Exception as e:
                logger.error(f"Error closing WS connection: {e}")
                raise
            finally:
                self.ws_client = None
                self.ws_transport = None
