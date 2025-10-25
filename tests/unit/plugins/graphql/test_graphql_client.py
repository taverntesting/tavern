from unittest.mock import Mock, patch

import pytest
import requests

from tavern._plugins.graphql.client import GraphQLClient


class TestGraphQLClient:
    def test_init_default(self):
        client = GraphQLClient()
        assert isinstance(client.session, requests.Session)
        assert client.default_headers == {}
        assert client.timeout == 30
        assert client.ws_url is None

    def test_init_with_kwargs(self):
        kwargs = {
            "headers": {"Authorization": "Bearer token"},
            "timeout": 60,
            "ws_url": "ws://localhost:4000/graphql",
        }
        client = GraphQLClient(**kwargs)
        assert client.default_headers == {"Authorization": "Bearer token"}
        assert client.timeout == 60
        assert client.ws_url == "ws://localhost:4000/graphql"

    def test_update_session_headers(self):
        client = GraphQLClient()
        client.update_session(headers={"X-Custom": "value"})
        assert "X-Custom" in client.session.headers

    @patch.object(requests.Session, "post")
    def test_make_request_post(self, mock_post):
        mock_response = Mock()
        mock_response.text = '{"data": {"hello": "world"}}'
        mock_post.return_value = mock_response

        client = GraphQLClient()
        response = client.make_request(
            url="http://example.com/graphql",
            query="query { hello }",
            variables={"name": "world"},
        )

        mock_post.assert_called_once()
        call_args = mock_post.call_args
        assert call_args[1]["json"]["query"] == "query { hello }"
        assert call_args[1]["json"]["variables"] == {"name": "world"}
        assert "Content-Type" in call_args[1]["headers"]
        assert response.text == '{"data": {"hello": "world"}}'

    @patch.object(requests.Session, "get")
    def test_make_request_get(self, mock_get):
        mock_response = Mock()
        mock_response.text = '{"data": {"hello": "world"}}'
        mock_get.return_value = mock_response

        client = GraphQLClient()
        response = client.make_request(
            url="http://example.com/graphql", query="query { hello }", method="GET"
        )

        mock_get.assert_called_once()
        call_args = mock_get.call_args
        assert call_args[1]["params"]["query"] == "query { hello }"
        assert "Content-Type" in call_args[1]["headers"]
        assert response.text == '{"data": {"hello": "world"}}'

    def test_subscription_not_implemented(self):
        client = GraphQLClient()
        with pytest.raises(
            NotImplementedError,
            match="GraphQL subscriptions will be implemented in a later phase",
        ):
            with client.subscription(
                "http://example.com/graphql", "subscription { hello }"
            ):
                pass
