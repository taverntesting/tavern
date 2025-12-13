import asyncio
from unittest.mock import Mock, patch

import gql
import pytest

from tavern._plugins.graphql.client import GraphQLClient


class TestGraphQLClient:
    def test_init_with_kwargs(self):
        kwargs = {
            "headers": {"Authorization": "Bearer token"},
            "timeout": 60,
        }
        client = GraphQLClient(**kwargs)
        assert client.default_headers == {"Authorization": "Bearer token"}
        assert client.timeout == 60

    def test_start_subscription(self):
        """Test starting a GraphQL subscription"""
        client = GraphQLClient(headers={"Authorization": "Bearer token"}, timeout=30)

        # Mock the WebsocketsTransport and Client
        with (
            patch(
                "tavern._plugins.graphql.client.WebsocketsTransport"
            ) as mock_ws_transport,
            patch("tavern._plugins.graphql.client.Client") as mock_client_class,
            patch("tavern._plugins.graphql.client.gql") as mock_gql,
        ):
            # Setup mock transport
            mock_transport_instance = Mock(spec=["close"])
            mock_ws_transport.return_value = mock_transport_instance

            # Setup mock client
            mock_client_instance = Mock(spec=["subscribe_async", "close_sync"])
            mock_client_class.return_value = mock_client_instance

            # Setup mock async subscription generator
            mock_subscription_gen = Mock()
            mock_client_instance.subscribe_async.return_value = mock_subscription_gen

            # Setup mock gql query
            mock_gql_query = Mock(spec=gql.GraphQLRequest)
            mock_gql.return_value = mock_gql_query

            # Call start_subscription
            url = "http://example.com/graphql"
            query = "subscription Test { testField }"
            variables = {"id": 123}
            operation_name = "Test"

            with client:  # Use the client context manager to set up the event loop
                client.start_subscription(url, query, variables, operation_name)

            # Assertions
            mock_ws_transport.assert_called_once_with(
                url="ws://example.com/graphql",
                headers={"Authorization": "Bearer token"},
                connect_timeout=30,
            )
            mock_client_class.assert_called_once_with(transport=mock_transport_instance)
            mock_gql.assert_called_once_with(query)
            mock_client_instance.subscribe_async.assert_called_once_with(
                mock_gql_query,
            )
            assert operation_name in client.subscriptions
            assert client.subscriptions[operation_name] == mock_subscription_gen

    def test_start_subscription_requires_operation_name(self):
        """Test that starting a subscription requires operation_name"""
        client = GraphQLClient()

        with (
            patch("tavern._plugins.graphql.client.WebsocketsTransport"),
            patch("tavern._plugins.graphql.client.Client"),
            patch("tavern._plugins.graphql.client.gql"),
        ):
            # Should raise ValueError when operation_name is None
            with pytest.raises(ValueError) as exc_info:
                client.start_subscription(
                    "ws://example.com", "subscription Test { test }", {}, None
                )
            assert "operation_name required for subscriptions" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_next_message_not_found(self):
        """Test getting next message from non-existent subscription"""
        client = GraphQLClient()

        with pytest.raises(ValueError) as exc_info:
            await client.get_next_message("non_existent")
        assert "Subscription with name 'non_existent' not found" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_get_next_message_success(self):
        """Test getting next message from subscription successfully"""
        client = GraphQLClient()

        # Create a mock async generator for the subscription
        async def mock_async_gen():
            yield {"data": {"test": "value"}}

        client.subscriptions["test_op"] = mock_async_gen()

        # Test getting the next message
        with client:  # Use context manager to set up the event loop
            message = await client.get_next_message("test_op")
        assert message == {"data": {"test": "value"}}

    @pytest.mark.asyncio
    async def test_get_next_message_timeout(self):
        """Test getting next message times out"""
        client = GraphQLClient()

        # Create a mock async generator that will timeout
        async def slow_async_gen():
            await asyncio.sleep(10)  # This will cause timeout
            yield {"data": {"test": "value"}}

        # Add the mock generator to subscriptions
        client.subscriptions["slow_op"] = slow_async_gen()

        # Test that timeout is raised
        with client:  # Use context manager to set up the event loop
            with pytest.raises(TimeoutError):
                await client.get_next_message("slow_op", timeout=0.1)

    @pytest.mark.asyncio
    async def test_get_next_message_exception(self):
        """Test getting next message when an exception occurs"""
        client = GraphQLClient()

        # Create a mock async generator that raises an exception
        async def error_async_gen():
            raise Exception("Test error")
            yield

        client.subscriptions["error_op"] = error_async_gen()

        # Test that the exception is propagated
        with client:  # Use context manager to set up the event loop
            with pytest.raises(Exception) as exc_info:
                await client.get_next_message("error_op")
        assert "Test error" in str(exc_info.value)
