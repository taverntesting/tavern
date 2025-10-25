from unittest.mock import MagicMock, Mock, patch

import pytest
import requests
import websockets

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

    def test_subscription_no_websockets_library(self):
        """Test subscription raises ImportError when websockets library is not available"""
        with patch("tavern._plugins.graphql.client.websockets", None):
            client = GraphQLClient()
            with pytest.raises(
                ImportError,
                match="websockets library is required for GraphQL subscriptions",
            ):
                with client.subscription(
                    "http://example.com/graphql", "subscription { hello }"
                ):
                    pass

    def test_subscription_connection_lifecycle(self):
        """Test WebSocket subscription connection lifecycle"""
        with patch("tavern._plugins.graphql.client.websockets") as mock_websockets:
            # Mock WebSocket connection
            mock_ws_connect = MagicMock()
            mock_websockets.connect.return_value = mock_ws_connect
            mock_connection = MagicMock()
            mock_ws_connect.__enter__.return_value = mock_connection

            client = GraphQLClient()

            with client.subscription(
                "ws://example.com/graphql",
                "subscription { hello }",
                {"variable": "value"},
            ) as subscription:
                # Verify connection was established
                mock_websockets.connect.assert_called_once_with(
                    "ws://example.com/graphql"
                )

                # Verify subscription start message was sent
                expected_start_payload = {
                    "type": "start",
                    "payload": {
                        "query": "subscription { hello }",
                        "variables": {"variable": "value"},
                    },
                }
                mock_connection.send.assert_called_once()
                sent_message = mock_connection.send.call_args[0][0]
                import json

                assert json.loads(sent_message) == expected_start_payload

                # Test receive method
                mock_connection.recv.return_value = (
                    '{"type": "data", "payload": {"data": {"hello": "world"}}}'
                )
                message = subscription.receive()
                assert message == {
                    "type": "data",
                    "payload": {"data": {"hello": "world"}},
                }

                # Test receive with timeout
                mock_connection.recv.return_value = '{"type": "complete"}'
                message = subscription.receive(timeout=5.0)
                assert message == {"type": "complete"}

    def test_subscription_connection_error_handling(self):
        """Test WebSocket subscription error handling"""
        with patch("tavern._plugins.graphql.client.websockets") as mock_websockets:
            mock_ws_connect = MagicMock()
            mock_websockets.connect.return_value = mock_ws_connect
            mock_connection = MagicMock()
            mock_ws_connect.__enter__.return_value = mock_connection

            client = GraphQLClient()

            # Test receive error
            mock_connection.recv.side_effect = Exception("Connection error")

            with client.subscription(
                "ws://example.com/graphql", "subscription { hello }"
            ) as subscription:
                with pytest.raises(
                    RuntimeError, match="Failed to receive WebSocket message"
                ):
                    subscription.receive()

    def test_subscription_close_handling(self):
        """Test WebSocket subscription close handling"""
        with patch("tavern._plugins.graphql.client.websockets") as mock_websockets:
            mock_ws_connect = MagicMock(spec_set=websockets.connect)
            mock_websockets.connect.return_value = mock_ws_connect
            mock_connection = MagicMock()
            mock_ws_connect.__enter__.return_value = mock_connection

            client = GraphQLClient()

            with client.subscription(
                "ws://example.com/graphql", "subscription { hello }"
            ) as subscription:
                pass  # Context manager should handle cleanup

            # Verify complete message was sent and connection closed
            complete_calls = [
                call
                for call in mock_connection.send.call_args_list
                if "complete" in str(call)
            ]
            assert len(complete_calls) == 1
            mock_ws_connect.__exit__.assert_called_once()
