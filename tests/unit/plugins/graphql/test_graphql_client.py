from unittest.mock import Mock, patch

import requests

from tavern._plugins.graphql.client import GraphQLClient


class TestGraphQLClient:
    def test_init_default(self):
        client = GraphQLClient()
        assert isinstance(client.session, requests.Session)
        assert client.default_headers == {}
        assert client.timeout == 30

    def test_init_with_kwargs(self):
        kwargs = {
            "headers": {"Authorization": "Bearer token"},
            "timeout": 60,
        }
        client = GraphQLClient(**kwargs)
        assert client.default_headers == {"Authorization": "Bearer token"}
        assert client.timeout == 60

    def test_update_session_headers(self):
        client = GraphQLClient()
        client.update_session(headers={"X-Custom": "value"})
        assert "X-Custom" in client.session.headers

    def test_make_request_post(self):
        with patch.object(requests.Session, "post") as mock_post:
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

    def test_make_request_get(self):
        with patch.object(requests.Session, "get") as mock_get:
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
