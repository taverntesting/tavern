import logging

import box

from tavern._core import exceptions
from tavern._core.dict_util import format_keys
from tavern._core.pytest.config import TestConfig
from tavern.request import BaseRequest

from .client import GraphQLClient

logger: logging.Logger = logging.getLogger(__name__)


def _format_graphql_request(rspec: dict, variables: dict) -> dict:
    """Format a GraphQL request spec, excluding the query field from formatting.

    GraphQL queries contain curly braces which are mistakenly interpreted as format
    placeholders by the standard format_keys function. This function formats all
    fields except the query field to preserve the GraphQL syntax.

    Args:
        rspec: Request specification dictionary
        variables: Variables to format with

    Returns:
        Formatted request specification with query field unchanged
    """
    formatted_rspec = {}

    for key, value in rspec.items():
        if key == "query":
            # Skip formatting for GraphQL queries to preserve { } syntax
            formatted_rspec[key] = value
        elif key == "operation_name" and value is not None:
            # Format operation_name if it exists and is not None
            formatted_rspec[key] = format_keys(value, variables)
        else:
            # Format all other fields normally
            formatted_rspec[key] = format_keys(value, variables)

    return formatted_rspec


class GraphQLRequest(BaseRequest):
    """GraphQL request implementation"""

    def __init__(
        self, session: GraphQLClient, rspec: dict, test_block_config: TestConfig
    ):
        self.session = session
        self.rspec = rspec
        self.test_block_config = test_block_config

        # Format request spec with test variables, excluding query from formatting
        self._formatted_rspec = _format_graphql_request(
            rspec, test_block_config.variables
        )

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

            # Check if this is a subscription request
            if self._is_subscription_query():
                return self._run_subscription()
            else:
                return self._run_query()

        except Exception as e:
            logger.exception("Error executing GraphQL request")
            raise exceptions.TavernException(f"GraphQL request failed: {e}") from e

    def _is_subscription_query(self) -> bool:
        """Check if the query is a subscription"""
        query = self._formatted_rspec.get("query", "").strip()
        # Simple check for subscription keyword at the start of the query
        return query.lower().startswith("subscription")

    def _run_query(self):
        """Execute regular GraphQL query/mutation"""
        response = self.session.make_request(
            url=self._formatted_rspec["url"],
            query=self._formatted_rspec["query"],
            variables=self._formatted_rspec.get("variables"),
            operation_name=self._formatted_rspec.get("operation_name"),
        )

        logger.debug("GraphQL response: %s", response.text)
        return response

    def _run_subscription(self):
        """Execute GraphQL subscription and return mock response for validation"""
        # For subscriptions, we establish the connection and return a mock response
        # The actual subscription testing happens in the response validation
        subscription_timeout = self._formatted_rspec.get("timeout", 30)

        try:
            with self.session.subscription(
                url=self._formatted_rspec["url"],
                query=self._formatted_rspec["query"],
                variables=self._formatted_rspec.get("variables"),
            ) as subscription:
                # Store the subscription connection for use in response validation
                self._subscription_connection = subscription

                # Create a mock response object for initial validation
                mock_response = _MockSubscriptionResponse()

                logger.debug("GraphQL subscription established")
                return mock_response

        except Exception as e:
            logger.exception("Error establishing GraphQL subscription")
            raise exceptions.TavernException(f"GraphQL subscription failed: {e}") from e


class _MockSubscriptionResponse:
    """Mock response object for GraphQL subscriptions"""

    def __init__(self):
        self.status_code = 200
        self.text = "Subscription established"
        self._messages = []

    def json(self):
        return {"data": None, "subscription": "established"}

    def add_message(self, message: dict):
        """Add a received subscription message"""
        self._messages.append(message)

    def get_messages(self) -> list:
        """Get all received subscription messages"""
        return self._messages.copy()
