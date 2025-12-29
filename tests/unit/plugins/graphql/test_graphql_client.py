import asyncio
from unittest.mock import AsyncMock, Mock, patch

import gql
import pytest
from gql.transport.aiohttp import AIOHTTPTransport

from tavern._plugins.graphql.client import GraphQLClient, TransportKey


class TestGraphQLClient:
    def test_init_with_kwargs(self):
        kwargs = {
            "headers": {"Authorization": "Bearer token"},
            "timeout": 60,
        }
        client = GraphQLClient(**kwargs)
        assert client.default_headers == {"Authorization": "Bearer token"}
        assert client.timeout == 60

    def test_start_subscription_success(self):
        """Test starting a subscription successfully"""
        client = GraphQLClient()

        # Mock the necessary components
        with (
            patch(
                "tavern._plugins.graphql.client.WebsocketsTransport"
            ) as mock_ws_transport,
            patch("tavern._plugins.graphql.client.gql") as mock_gql,
        ):
            # Set up the mock session and subscription generator
            mock_session = AsyncMock()
            mock_generator = AsyncMock()
            mock_session.__aenter__ = AsyncMock(return_value=mock_session)
            mock_session.__aexit__ = AsyncMock(return_value=None)
            mock_session.subscribe = Mock(return_value=mock_generator)

            mock_gql_obj = Mock()
            mock_gql.return_value = mock_gql_obj

            # Start a subscription with valid parameters
            with client:  # Use context manager to set up the event loop
                client.start_subscription(
                    url="https://example.com/graphql",
                    query="subscription Test { test }",
                    variables={"param": "value"},
                    operation_name="TestSubscription",
                )

            # Verify the subscription was created
            assert "TestSubscription" in client._subscriptions
            assert mock_ws_transport.called

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

        client._subscriptions["test_op"] = mock_async_gen()

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
        client._subscriptions["slow_op"] = slow_async_gen()

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

        client._subscriptions["error_op"] = error_async_gen()

        # Test that the exception is propagated
        with client:  # Use context manager to set up the event loop
            with pytest.raises(Exception) as exc_info:
                await client.get_next_message("error_op")
        assert "Test error" in str(exc_info.value)


class TestTransportKey:
    """Tests for the TransportKey class"""

    def test_transport_key_creation(self):
        """Test creating a TransportKey from components"""
        headers = {"Authorization": "Bearer token", "Content-Type": "application/json"}
        key = TransportKey(
            url="https://example.com/graphql",
            headers=headers,
            timeout=30,
        )
        assert key.url == "https://example.com/graphql"
        assert key.timeout == 30
        # Headers should be converted to sorted tuple
        assert isinstance(key.headers, tuple)
        assert ("Authorization", "Bearer token") in key.headers
        assert ("Content-Type", "application/json") in key.headers

    def test_transport_key_hashable(self):
        """Test that TransportKey instances are hashable"""
        headers1 = {"Authorization": "Bearer token"}
        headers2 = {"Authorization": "Bearer token"}
        headers3 = {"Authorization": "Different token"}

        key1 = TransportKey(
            url="https://example.com/graphql", headers=headers1, timeout=30
        )
        key2 = TransportKey(
            url="https://example.com/graphql", headers=headers2, timeout=30
        )
        key3 = TransportKey(
            url="https://example.com/graphql", headers=headers3, timeout=30
        )

        # Keys with same values should have same hash
        assert hash(key1) == hash(key2)

        # Keys with different values should have different hashes
        assert hash(key1) != hash(key3)

    def test_transport_key_equality(self):
        """Test TransportKey equality comparison"""
        headers1 = {"Authorization": "Bearer token"}
        headers2 = {"Authorization": "Bearer token"}
        headers3 = {"Authorization": "Different token"}

        key1 = TransportKey(
            url="https://example.com/graphql", headers=headers1, timeout=30
        )
        key2 = TransportKey(
            url="https://example.com/graphql", headers=headers2, timeout=30
        )
        key3 = TransportKey(
            url="https://example.com/graphql", headers=headers3, timeout=30
        )

        # Equal keys
        assert key1 == key2

        # Different keys
        assert key1 != key3
        assert key1 != "not a transport key"

    def test_transport_key_headers_order_independence(self):
        """Test that header order doesn't matter for TransportKey"""
        headers1 = {"Authorization": "Bearer token", "Content-Type": "application/json"}
        headers2 = {"Content-Type": "application/json", "Authorization": "Bearer token"}

        key1 = TransportKey(
            url="https://example.com/graphql", headers=headers1, timeout=30
        )
        key2 = TransportKey(
            url="https://example.com/graphql", headers=headers2, timeout=30
        )

        # Should be equal despite different ordering
        assert key1 == key2
        assert hash(key1) == hash(key2)

    def test_transport_key_repr(self):
        """Test TransportKey string representation"""
        headers = {"Authorization": "Bearer token"}
        key = TransportKey(
            url="https://example.com/graphql", headers=headers, timeout=30
        )
        repr_str = repr(key)
        assert "TransportKey" in repr_str
        assert "https://example.com/graphql" in repr_str


class TestTransportCaching:
    """Tests for HTTP transport caching functionality"""

    def test_make_request_creates_new_transport(self):
        """Test that first request creates a new transport"""
        client = GraphQLClient()

        query = """
            query TestQuery {
                user {
                    id
                }
            }
        """

        with patch("tavern._plugins.graphql.client.AIOHTTPTransport") as mock_transport:
            mock_transport_instance = Mock(spec=AIOHTTPTransport)
            mock_transport.return_value = mock_transport_instance

            with patch("tavern._plugins.graphql.client.Client") as mock_client:
                mock_execution_result = Mock()
                mock_execution_result.data = {"user": {"id": "1"}}
                mock_client_instance = Mock(spec=gql.Client)
                mock_client_instance.execute.return_value = mock_execution_result
                mock_client.return_value = mock_client_instance

                # Make a request
                response = client.make_request(
                    url="https://example.com/graphql",
                    query=query,
                )

                # Verify transport was created
                assert mock_transport.called
                assert len(client._http_transport_cache) == 1

                # Verify the response
                assert response.json() == {"user": {"id": "1"}}

    def test_make_request_reuses_cached_transport(self):
        """Test that subsequent requests to same URL reuse transport"""
        client = GraphQLClient()

        query1 = """
            query Query1 {
                user {
                    id
                }
            }
        """

        query2 = """
            query Query2 {
                posts {
                    id
                }
            }
        """

        with patch("tavern._plugins.graphql.client.AIOHTTPTransport") as mock_transport:
            mock_transport_instance = Mock(spec=AIOHTTPTransport)
            mock_transport.return_value = mock_transport_instance

            with patch("tavern._plugins.graphql.client.Client") as mock_client:
                mock_execution_result = Mock()
                mock_execution_result.data = {"data": "result"}
                mock_client_instance = Mock(spec=gql.Client)
                mock_client_instance.execute.return_value = mock_execution_result
                mock_client.return_value = mock_client_instance

                # Make first request
                client.make_request(
                    url="https://example.com/graphql",
                    query=query1,
                )

                # Make second request to same URL
                client.make_request(
                    url="https://example.com/graphql",
                    query=query2,
                )

                # Verify transport was created only once
                assert mock_transport.call_count == 1
                assert len(client._http_transport_cache) == 1

    def test_make_request_different_urls_create_different_transports(self):
        """Test that requests to different URLs create different transports"""
        client = GraphQLClient()

        query = """
            query TestQuery {
                user {
                    id
                }
            }
        """

        with patch("tavern._plugins.graphql.client.AIOHTTPTransport") as mock_transport:
            mock_transport_instance = Mock(spec=AIOHTTPTransport)
            mock_transport.return_value = mock_transport_instance

            with patch("tavern._plugins.graphql.client.Client") as mock_client:
                mock_execution_result = Mock()
                mock_execution_result.data = {"data": "result"}
                mock_client_instance = Mock(spec=gql.Client)
                mock_client_instance.execute.return_value = mock_execution_result
                mock_client.return_value = mock_client_instance

                # Make requests to different URLs
                client.make_request(
                    url="https://example.com/graphql",
                    query=query,
                )

                client.make_request(
                    url="https://another-example.com/graphql",
                    query=query,
                )

                # Verify two transports were created
                assert mock_transport.call_count == 2
                assert len(client._http_transport_cache) == 2

    def test_make_request_different_headers_create_different_transports(self):
        """Test that requests with different headers create different transports"""
        client = GraphQLClient()

        query = """
            query TestQuery {
                user {
                    id
                }
            }
        """

        with patch("tavern._plugins.graphql.client.AIOHTTPTransport") as mock_transport:
            mock_transport_instance = Mock(spec=AIOHTTPTransport)
            mock_transport.return_value = mock_transport_instance

            with patch("tavern._plugins.graphql.client.Client") as mock_client:
                mock_execution_result = Mock()
                mock_execution_result.data = {"data": "result"}
                mock_client_instance = Mock(spec=gql.Client)
                mock_client_instance.execute.return_value = mock_execution_result
                mock_client.return_value = mock_client_instance

                # Make first request with Authorization header
                client.make_request(
                    url="https://example.com/graphql",
                    query=query,
                    headers={"Authorization": "Bearer token1"},
                )

                # Make second request with different Authorization header
                client.make_request(
                    url="https://example.com/graphql",
                    query=query,
                    headers={"Authorization": "Bearer token2"},
                )

                # Verify two transports were created (different headers)
                assert mock_transport.call_count == 2
                assert len(client._http_transport_cache) == 2

    def test_make_request_same_headers_reuse_transport(self):
        """Test that requests with same headers reuse transport"""
        client = GraphQLClient()

        query = """
            query TestQuery {
                user {
                    id
                }
            }
        """

        with patch("tavern._plugins.graphql.client.AIOHTTPTransport") as mock_transport:
            mock_transport_instance = Mock(spec=AIOHTTPTransport)
            mock_transport.return_value = mock_transport_instance

            with patch("tavern._plugins.graphql.client.Client") as mock_client:
                mock_execution_result = Mock()
                mock_execution_result.data = {"data": "result"}
                mock_client_instance = Mock(spec=gql.Client)
                mock_client_instance.execute.return_value = mock_execution_result
                mock_client.return_value = mock_client_instance

                # Make two requests with same headers
                client.make_request(
                    url="https://example.com/graphql",
                    query=query,
                    headers={"Authorization": "Bearer token"},
                )

                client.make_request(
                    url="https://example.com/graphql",
                    query=query,
                    headers={"Authorization": "Bearer token"},
                )

                # Verify only one transport was created
                assert mock_transport.call_count == 1
                assert len(client._http_transport_cache) == 1

    def test_client_context_manager_closes_cached_transports(self):
        """Test that context manager exit closes cached transports"""
        client = GraphQLClient()

        with patch("tavern._plugins.graphql.client.AIOHTTPTransport") as mock_transport:
            mock_transport_instance = Mock(spec=AIOHTTPTransport)
            mock_transport.return_value = mock_transport_instance

            with patch("tavern._plugins.graphql.client.Client") as mock_client:
                mock_execution_result = Mock()
                mock_execution_result.data = {"data": "result"}
                mock_client_instance = Mock(spec=gql.Client)
                mock_client_instance.execute.return_value = mock_execution_result
                mock_client.return_value = mock_client_instance

                # Use context manager and make a request
                with client:
                    client.make_request(
                        url="https://example.com/graphql",
                        query="query { test }",
                    )

                # Verify transport.close() was called on exit
                assert mock_transport_instance.close.called
