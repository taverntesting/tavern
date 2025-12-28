import logging
from contextlib import ExitStack
from functools import cached_property

import box
import gql.transport.exceptions
from gql import FileVar

from tavern._core import exceptions
from tavern._core.dict_util import deep_dict_merge, format_keys
from tavern._core.files import guess_filespec
from tavern._core.formatted_str import FormattedString
from tavern._core.pytest.config import TestConfig
from tavern.request import BaseRequest

from .client import GraphQLClient, GraphQLResponseLike

logger: logging.Logger = logging.getLogger(__name__)


def get_file_arguments(file_args: dict, test_block_config: TestConfig) -> dict:
    """Get correct arguments for anything that should be passed as a file to
    gql

    Args:
        file_args: dict of files to upload
        test_block_config: config for test

    Returns:
        mapping of 'files' block to pass directly to gql
    """

    # Note: Not actually using the opened files
    gql_file_vars = {}
    with ExitStack() as stack:
        for var_name, file_path_or_long_format in file_args.items():
            file_spec, form_field_name, resolved_file_path = guess_filespec(
                file_path_or_long_format, stack, test_block_config
            )
            if form_field_name is None:
                form_field_name = var_name

            if form_field_name in gql_file_vars:
                raise exceptions.BadSchemaError(
                    f"Cannot upload multiple files with the same name '{form_field_name}'"
                )

            gql_file_var = FileVar(
                f=resolved_file_path,
                filename=form_field_name,
                content_type=file_spec.content_type,
            )
            gql_file_vars[var_name] = gql_file_var

    return gql_file_vars


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
            formatted_rspec[key] = FormattedString(value)
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

        if self.is_subscription_query and "operation_name" not in self._formatted_rspec:
            raise exceptions.MissingKeysError(
                "operation_name is required for subscription requests"
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
            url = str(self._formatted_rspec["url"])
            query = str(self._formatted_rspec["query"])
            variables = self._formatted_rspec.get("variables", {}) or {}
            operation_name = self._formatted_rspec.get("operation_name")

            headers = {}
            files = self._formatted_rspec.get("files")
            if files:
                variables.update(get_file_arguments(files, self.test_block_config))
            else:
                headers["Content-Type"] = "application/json"

            logger.debug(f"graphql variables: {variables}")

            headers = deep_dict_merge(headers, self._formatted_rspec.get("headers", {}))

            if self.is_subscription_query:
                self.session.start_subscription(url, query, variables, operation_name)
                fake_resp = GraphQLResponseLike(result=None)
                logger.debug(
                    "Subscription '%s' started, fake 101 response", operation_name
                )
                return fake_resp

            # Execute regular GraphQL query/mutation
            response = self.session.make_request(
                url=url,
                query=query,
                variables=variables,
                operation_name=operation_name,
                headers=headers,
                has_files=files is not None,
            )

            logger.debug("GraphQL response: %s", response.text)
            return response

        except gql.transport.exceptions.TransportQueryError as e:
            logger.debug("graphql error while making request: %s", e)
            return GraphQLResponseLike(result=e)
        except Exception as e:
            logger.exception("Error executing GraphQL request")
            raise exceptions.TavernException(f"GraphQL request failed: {e}") from e

    @cached_property
    def is_subscription_query(self) -> bool:
        """Check if the query is a subscription"""
        query = self._formatted_rspec.get("query", "").strip()
        # Simple check for subscription keyword at the start of the query
        return query.lower().startswith("subscription")
