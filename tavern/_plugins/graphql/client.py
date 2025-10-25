import json
import logging
from typing import Any, Optional

import requests

logger: logging.Logger = logging.getLogger(__name__)


class GraphQLClient:
    """GraphQL client for HTTP requests"""

    def __init__(self, **kwargs):
        self.session = requests.Session()
        self.default_headers = kwargs.get("headers", {})
        self.timeout = kwargs.get("timeout", 30)

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
