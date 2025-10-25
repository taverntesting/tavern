import json
import logging
from contextlib import contextmanager
from typing import Any, Optional

import requests

try:
    import websockets
except ImportError:
    websockets = None

logger: logging.Logger = logging.getLogger(__name__)


class _SubscriptionConnection:
    def __init__(
        self,
        ws_url: str,
        gql_query: str,
        gql_variables: Optional[dict[str, Any]],
    ):
        self.ws_url = ws_url
        self.query = gql_query
        self.variables = gql_variables or {}
        self.ws_connection = None

    def connect(self):
        """Establish WebSocket connection and send subscription query"""
        self.ws_connection = websockets.connect(self.ws_url)
        conn = self.ws_connection.__enter__()

        # Send subscription start message
        start_payload = {
            "type": "start",
            "payload": {
                "query": self.query,
                "variables": self.variables,
            },
        }
        conn.send(json.dumps(start_payload))
        return conn

    def receive(self, timeout: Optional[float] = None) -> dict:
        """Receive a message from the subscription"""
        if self.ws_connection is None:
            raise RuntimeError("WebSocket connection not established")

        try:
            message = self.ws_connection.recv(timeout=timeout)
            return json.loads(message)
        except Exception as e:
            raise RuntimeError(f"Failed to receive WebSocket message: {e}") from e

    def close(self):
        """Close the WebSocket connection"""
        if self.ws_connection:
            try:
                # Send complete message
                complete_payload = {"type": "complete"}
                self.ws_connection.send(json.dumps(complete_payload))
                self.ws_connection.__exit__(None, None, None)
            except Exception as e:
                logger.warning("Error closing WebSocket connection: %s", e)
            finally:
                self.ws_connection = None


class GraphQLClient:
    """GraphQL client for HTTP requests and WebSocket connections"""

    def __init__(self, **kwargs):
        self.session = requests.Session()
        self.default_headers = kwargs.get("headers", {})
        self.timeout = kwargs.get("timeout", 30)
        self.ws_url = kwargs.get("ws_url")

    def __enter__(self):
        return self.session.__enter__()

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.__exit__(exc_type, exc_val, exc_tb)

    def update_session(self, **kwargs):
        """Update session with new configuration"""
        if "headers" in kwargs:
            self.session.headers.update(kwargs["headers"])

    def make_request(
        self,
        url: str,
        query: str,
        variables: Optional[dict[str, Any]] = None,
        operation_name: Optional[str] = None,
        method: str = "POST",
    ) -> requests.Response:
        """Execute GraphQL query over HTTP using raw requests"""
        payload = {
            "query": query,
            "variables": variables or {},
        }

        if operation_name:
            payload["operationName"] = operation_name

        headers = dict(self.default_headers)
        headers.update({"Content-Type": "application/json"})

        if method.upper() == "GET":
            # For GET requests, encode query in URL parameters
            params = {"query": query}
            if variables:
                params["variables"] = json.dumps(variables)
            if operation_name:
                params["operationName"] = operation_name

            return self.session.get(
                url, params=params, headers=headers, timeout=self.timeout
            )
        else:
            # Default to POST for GraphQL queries
            return self.session.post(
                url, json=payload, headers=headers, timeout=self.timeout
            )

    @contextmanager
    def subscription(
        self, url: str, query: str, variables: Optional[dict[str, Any]] = None
    ):
        """Context manager for GraphQL subscriptions over WebSocket"""
        if websockets is None:
            raise ImportError(
                "websockets library is required for GraphQL subscriptions. "
                "Install with: pip install tavern[graphql-ws]"
            )

        websocket_url = url.replace("http://", "ws://").replace("https://", "wss://")

        subscription_conn = _SubscriptionConnection(websocket_url, query, variables)

        try:
            subscription_conn.connect()
            yield subscription_conn
        finally:
            subscription_conn.close()
