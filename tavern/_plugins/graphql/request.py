import logging

import box

from tavern._core import exceptions
from tavern._core.dict_util import format_keys
from tavern._core.pytest.config import TestConfig
from tavern.request import BaseRequest

from .client import GraphQLClient

logger: logging.Logger = logging.getLogger(__name__)


class GraphQLRequest(BaseRequest):
    """GraphQL request implementation"""

    def __init__(
        self, session: GraphQLClient, rspec: dict, test_block_config: TestConfig
    ):
        self.session = session
        self.rspec = rspec
        self.test_block_config = test_block_config

        # Format request spec with test variables
        self._formatted_rspec = format_keys(rspec, test_block_config.variables)

        # Validate required fields
        self._validate_request()

    def _validate_request(self):
        """Validate GraphQL request structure"""
        if "query" not in self._formatted_rspec:
            raise exceptions.MissingKeysError(
                "GraphQL request must contain 'query' field"
            )

        if "url" not in self._formatted_rspec:
            raise exceptions.MissingKeysError(
                "GraphQL request must contain 'url' field"
            )

    @property
    def request_vars(self) -> box.Box:
        """Variables used in the request"""
        return box.Box(
            {
                "url": self._formatted_rspec["url"],
                "query": self._formatted_rspec["query"],
                "variables": self._formatted_rspec.get("variables", {}),
                "operation_name": self._formatted_rspec.get("operation_name"),
                "headers": self._formatted_rspec.get("headers", {}),
            }
        )

    def run(self):
        """Execute GraphQL request"""
        try:
            # Update session headers if provided
            if "headers" in self._formatted_rspec:
                self.session.update_session(headers=self._formatted_rspec["headers"])

            # Execute request
            response = self.session.make_request(
                url=self._formatted_rspec["url"],
                query=self._formatted_rspec["query"],
                variables=self._formatted_rspec.get("variables"),
                operation_name=self._formatted_rspec.get("operation_name"),
            )

            logger.debug("GraphQL response: %s", response.text)
            return response

        except Exception as e:
            logger.exception("Error executing GraphQL request")
            raise exceptions.TavernException(f"GraphQL request failed: {e}") from e
