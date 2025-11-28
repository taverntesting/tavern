import json
import logging
from typing import Any, Optional

from _plugins.common.response import ResponseLike
from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport
from gql.transport.websockets import WebsocketsTransport
from graphql import ExecutionResult

logger: logging.Logger = logging.getLogger(__name__)


class GraphQLResponseLike(ResponseLike):
    """A response-like object implementing the ResponseLike protocol for GraphQL responses"""

    def __init__(self, status_code: int, reason: str, headers: dict, text: str):
        self.status_code = status_code
        self.reason = reason
        self.headers = headers
        self.text = text
        self._json = None

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

    def __init__(self, **kwargs):
        self.default_headers = kwargs.get("headers", {})
        self.timeout = kwargs.get("timeout", 30)

        # For managing separate clients for HTTP and WebSocket connections
        self.http_client = None
        self.ws_client = None
        self.ws_transport = None

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

        try:
            result: ExecutionResult = self.http_client.execute(
                query_gql,
                variable_values=variables or {},
                operation_name=operation_name,
                get_execution_result=True,
            )
            body_dict = {}
            if result.data:
                body_dict["data"] = result.data
            if result.errors:
                body_dict["errors"] = result.errors
            text = json.dumps(body_dict)
            status_code = 200
            reason = "OK"
        except Exception as exc:
            status_code = 500
            reason = "Internal Server Error"
            body_dict = {"errors": [{"message": str(exc)}]}
            text = json.dumps(body_dict)

        response_headers = {"Content-Type": "application/json"}

        return GraphQLResponseLike(status_code, reason, response_headers, text)

    def start_subscription(
        self, url: str, query: str, variables: dict, operation_name: str
    ):
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
            timeout=self.timeout,
        )

        # Create client with WebSocket transport
        self.ws_client = Client(transport=self.ws_transport)

        # Parse the GraphQL query
        query_gql = gql(query)

        # Execute the subscription - this returns a generator
        try:
            # Using the subscription as a generator that yields results
            subscription_generator = self.ws_client.subscribe(
                query_gql,
                variable_values=variables or {},
                operation_name=operation_name,
            )

            logger.debug(f"Started subscription {operation_name}")
            # Return the generator to allow iterating through subscription messages
            return subscription_generator
        except Exception as exc:
            logger.error(f"Failed to start subscription: {exc}")
            raise

    def get_next_message(
        self, subscription_generator, timeout: float = 5.0
    ) -> Optional[dict]:
        """
        Get next message from subscription generator.
        Note: timeout parameter is ignored in this implementation as the generator
        is synchronous and will block until the next message is available.
        """
        try:
            # Get the next result from the subscription generator
            result = next(subscription_generator)
            return result
        except StopIteration:
            # Subscription ended
            return None
        except Exception as e:
            logger.error(f"Error getting next message from subscription: {e}")
            return None

    def _close_ws(self):
        """Close WS connection"""
        if self.ws_client:
            try:
                # Close the WebSocket client
                self.ws_client.close()
                logger.debug("WS connection closed")
            except Exception as e:
                logger.error(f"Error closing WS connection: {e}")
            finally:
                self.ws_client = None
                self.ws_transport = None
