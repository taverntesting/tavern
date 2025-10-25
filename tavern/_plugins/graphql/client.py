import json
import logging
from contextlib import contextmanager
from typing import Any, Optional

import requests

logger: logging.Logger = logging.getLogger(__name__)


class GraphQLClient:
    """GraphQL client for HTTP requests and WebSocket connections"""

    def __init__(self, **kwargs):
        self.session = requests.Session()
        self.default_headers = kwargs.get("headers", {})
        self.timeout = kwargs.get("timeout", 30)
        self.ws_url = kwargs.get("ws_url")

    def __enter__(self) -> "GraphQLClient":
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.session.close()

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
        # WebSocket support can be added in a later phase
        ws_url = url.replace("http://", "ws://").replace("https://", "wss://")

        payload = {
            "type": "start",
            "payload": {
                "query": query,
                "variables": variables or {},
            },
        }

        # For now, this is a placeholder for future WebSocket implementation
        raise NotImplementedError(
            "GraphQL subscriptions will be implemented in a later phase"
        )
