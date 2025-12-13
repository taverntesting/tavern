from unittest.mock import Mock, patch

import pytest
import requests

from tavern._core import exceptions
from tavern._plugins.graphql.client import GraphQLClient
from tavern._plugins.graphql.request import GraphQLRequest


class TestGraphQLRequest:
    def test_init_valid_request(self, graphql_test_block_config):
        session = GraphQLClient()
        rspec = {
            "url": "http://example.com/graphql",
            "query": "query { hello }",
            "variables": {"name": "world"},
        }

        request = GraphQLRequest(session, rspec, graphql_test_block_config)

        assert request.request_vars.url == "http://example.com/graphql"
        assert request.request_vars.query == "query { hello }"
        assert request.request_vars.variables == {"name": "world"}

    def test_init_missing_query(self, graphql_test_block_config):
        session = GraphQLClient()
        rspec = {"url": "http://example.com/graphql", "variables": {"name": "world"}}

        with pytest.raises(
            exceptions.MissingKeysError,
            match="GraphQL request must contain 'query' field",
        ):
            GraphQLRequest(session, rspec, graphql_test_block_config)

    def test_init_missing_url(self, graphql_test_block_config):
        session = GraphQLClient()
        rspec = {"query": "query { hello }", "variables": {"name": "world"}}

        with pytest.raises(
            exceptions.MissingKeysError,
            match="GraphQL request must contain 'url' field",
        ):
            GraphQLRequest(session, rspec, graphql_test_block_config)

    def test_request_vars_defaults(self, graphql_test_block_config):
        session = GraphQLClient()
        rspec = {"url": "http://example.com/graphql", "query": "query { hello }"}

        request = GraphQLRequest(session, rspec, graphql_test_block_config)

        assert request.request_vars.variables == {}
        assert request.request_vars.operation_name is None
        assert request.request_vars.headers == {}

    def test_run_success(self, graphql_test_block_config):
        with (
            patch.object(GraphQLClient, "make_request") as mock_make_request,
        ):
            mock_response = Mock(spec=requests.Response)
            mock_response.text = '{"data": {"hello": "world"}}'
            mock_make_request.return_value = mock_response

            session = GraphQLClient()
            rspec = {
                "url": "http://example.com/graphql",
                "query": "query { hello }",
                "headers": {"Authorization": "Bearer token"},
            }

            request = GraphQLRequest(session, rspec, graphql_test_block_config)
            response = request.run()

            mock_make_request.assert_called_once_with(
                url="http://example.com/graphql",
                query="query { hello }",
                variables={},
                operation_name=None,
                headers={"Authorization": "Bearer token"},
            )
            assert response.text == '{"data": {"hello": "world"}}'

    def test_run_failure(self, graphql_test_block_config):
        with patch.object(GraphQLClient, "make_request") as mock_make_request:
            mock_make_request.side_effect = Exception("Connection error")

            session = GraphQLClient()
            rspec = {"url": "http://example.com/graphql", "query": "query { hello }"}

            request = GraphQLRequest(session, rspec, graphql_test_block_config)

            with pytest.raises(
                exceptions.TavernException,
                match="GraphQL request failed: Connection error",
            ):
                request.run()
