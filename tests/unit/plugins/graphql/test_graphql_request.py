from unittest.mock import Mock, patch

import pytest

from tavern._core import exceptions
from tavern._core.pytest.config import TavernInternalConfig, TestConfig
from tavern._core.strict_util import StrictLevel
from tavern._plugins.graphql.client import GraphQLClient
from tavern._plugins.graphql.request import GraphQLRequest


class TestGraphQLRequest:
    def test_init_valid_request(self):
        session = GraphQLClient()
        rspec = {
            "url": "http://example.com/graphql",
            "query": "query { hello }",
            "variables": {"name": "world"},
        }
        test_block_config = TestConfig(
            variables={},
            strict=StrictLevel.all_on(),
            tavern_internal=TavernInternalConfig(
                pytest_hook_caller=Mock(),
                backends={"graphql": "graphql"},
            ),
            follow_redirects=False,
            stages=[],
        )

        request = GraphQLRequest(session, rspec, test_block_config)

        assert request.request_vars.url == "http://example.com/graphql"
        assert request.request_vars.query == "query TestQuery { hello }"
        assert request.request_vars.variables == {"name": "world"}

    def test_init_missing_query(self):
        session = GraphQLClient()
        rspec = {"url": "http://example.com/graphql", "variables": {"name": "world"}}
        test_block_config = TestConfig(
            variables={},
            strict=StrictLevel.all_on(),
            tavern_internal=TavernInternalConfig(
                pytest_hook_caller=Mock(),
                backends={"graphql": "graphql"},
            ),
            follow_redirects=False,
            stages=[],
        )

        with pytest.raises(
            exceptions.MissingKeysError,
            match="GraphQL request must contain 'query' field",
        ):
            GraphQLRequest(session, rspec, test_block_config)

    def test_init_missing_url(self):
        session = GraphQLClient()
        rspec = {"query": "query { hello }", "variables": {"name": "world"}}
        test_block_config = TestConfig(
            variables={},
            strict=StrictLevel.all_on(),
            tavern_internal=TavernInternalConfig(
                pytest_hook_caller=Mock(),
                backends={"graphql": "graphql"},
            ),
            follow_redirects=False,
            stages=[],
        )

        with pytest.raises(
            exceptions.MissingKeysError,
            match="GraphQL request must contain 'url' field",
        ):
            GraphQLRequest(session, rspec, test_block_config)

    def test_request_vars_defaults(self):
        session = GraphQLClient()
        rspec = {"url": "http://example.com/graphql", "query": "query { hello }"}
        test_block_config = TestConfig(
            variables={},
            strict=StrictLevel.all_on(),
            tavern_internal=TavernInternalConfig(
                pytest_hook_caller=Mock(),
                backends={"graphql": "graphql"},
            ),
            follow_redirects=False,
            stages=[],
        )

        request = GraphQLRequest(session, rspec, test_block_config)

        assert request.request_vars.variables == {}
        assert request.request_vars.operation_name is None
        assert request.request_vars.headers == {}

    @patch.object(GraphQLClient, "make_request")
    @patch.object(GraphQLClient, "update_session")
    def test_run_success(self, mock_update_session, mock_make_request):
        mock_response = Mock()
        mock_response.text = '{"data": {"hello": "world"}}'
        mock_make_request.return_value = mock_response

        session = GraphQLClient()
        rspec = {
            "url": "http://example.com/graphql",
            "query": "query { hello }",
            "headers": {"Authorization": "Bearer token"},
        }
        test_block_config = TestConfig(
            variables={},
            strict=StrictLevel.all_on(),
            tavern_internal=TavernInternalConfig(
                pytest_hook_caller=Mock(),
                backends={"graphql": "graphql"},
            ),
            follow_redirects=False,
            stages=[],
        )

        request = GraphQLRequest(session, rspec, test_block_config)
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

    @patch.object(GraphQLClient, "make_request")
    def test_run_failure(self, mock_make_request):
        mock_make_request.side_effect = Exception("Connection error")

        session = GraphQLClient()
        rspec = {"url": "http://example.com/graphql", "query": "query { hello }"}
        test_block_config = TestConfig(
            variables={},
            strict=StrictLevel.all_on(),
            tavern_internal=TavernInternalConfig(
                pytest_hook_caller=Mock(),
                backends={"graphql": "graphql"},
            ),
            follow_redirects=False,
            stages=[],
        )

        request = GraphQLRequest(session, rspec, test_block_config)

        with pytest.raises(
            exceptions.TavernException, match="GraphQL request failed: Connection error"
        ):
            request.run()
