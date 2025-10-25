from unittest.mock import MagicMock, Mock, patch

import pytest

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
            patch.object(GraphQLClient, "update_session") as mock_update_session,
        ):
            mock_response = Mock()
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

            mock_update_session.assert_called_once_with(
                headers={"Authorization": "Bearer token"}
            )
            mock_make_request.assert_called_once_with(
                url="http://example.com/graphql",
                query="query { hello }",
                variables=None,
                operation_name=None,
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

    def test_is_subscription_query_true(self, graphql_test_block_config):
        """Test subscription query detection"""
        session = GraphQLClient()
        rspec = {"url": "http://example.com/graphql", "query": "subscription { hello }"}

        request = GraphQLRequest(session, rspec, graphql_test_block_config)
        assert request._is_subscription_query() is True

    def test_is_subscription_query_false(self, graphql_test_block_config):
        """Test regular query is not detected as subscription"""
        session = GraphQLClient()
        rspec = {"url": "http://example.com/graphql", "query": "query { hello }"}

        request = GraphQLRequest(session, rspec, graphql_test_block_config)
        assert request._is_subscription_query() is False

    def test_is_subscription_query_mixed_case(self, graphql_test_block_config):
        """Test subscription query detection with mixed case"""
        session = GraphQLClient()
        rspec = {"url": "http://example.com/graphql", "query": "Subscription { hello }"}

        request = GraphQLRequest(session, rspec, graphql_test_block_config)
        assert request._is_subscription_query() is True

    def test_run_subscription_success(self, graphql_test_block_config):
        """Test successful subscription execution"""
        with patch.object(GraphQLClient, "subscription") as mock_subscription:
            mock_connection = MagicMock()
            mock_subscription.return_value.__enter__.return_value = mock_connection

            session = GraphQLClient()
            rspec = {
                "url": "http://example.com/graphql",
                "query": "subscription { hello }",
                "variables": {"name": "world"},
            }

            request = GraphQLRequest(session, rspec, graphql_test_block_config)
            response = request.run()

            # Verify subscription was called with correct parameters
            mock_subscription.assert_called_once_with(
                url="http://example.com/graphql",
                query="subscription { hello }",
                variables={"name": "world"},
            )

            # Verify mock response was returned
            assert hasattr(response, "status_code")
            assert response.status_code == 200
            assert response.text == "Subscription established"

    def test_run_subscription_failure(self, graphql_test_block_config):
        """Test subscription execution failure"""
        with patch.object(GraphQLClient, "subscription") as mock_subscription:
            mock_subscription.side_effect = Exception("WebSocket connection failed")

            session = GraphQLClient()
            rspec = {
                "url": "http://example.com/graphql",
                "query": "subscription { hello }",
            }

            request = GraphQLRequest(session, rspec, graphql_test_block_config)

            with pytest.raises(
                exceptions.TavernException,
                match="GraphQL subscription failed: WebSocket connection failed",
            ):
                request.run()
