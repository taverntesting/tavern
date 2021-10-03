from unittest.mock import MagicMock, Mock, patch

import paho.mqtt.client as paho
import pytest

from tavern._core import exceptions
from tavern._plugins.mqtt.client import MQTTClient, _handle_tls_args
from tavern._plugins.mqtt.request import MQTTRequest


def test_host_required():
    """Always needs a host, but it's the only required key"""
    with pytest.raises(exceptions.MissingKeysError):
        MQTTClient()

    args = {"connect": {"host": "localhost"}}

    MQTTClient(**args)


class TestClient(object):
    @pytest.fixture(name="fake_client")
    def fix_fake_client(self):
        args = {"connect": {"host": "localhost"}}

        return MQTTClient(**args)

    def test_no_message(self, fake_client):
        """No message in queue returns None"""

        assert fake_client.message_received(0) is None

    def test_message_queued(self, fake_client):
        """Returns message in queue"""

        message = "abc123"

        fake_client._userdata["queue"].put(message)
        assert fake_client.message_received(0) == message

    def test_context_connection_failure(self, fake_client):
        """Unable to connect on __enter__ raises MQTTError"""

        fake_client._connect_timeout = 0.3

        with patch.object(fake_client._client, "loop_start"):
            with pytest.raises(exceptions.MQTTError):
                with fake_client:
                    pass

    def test_context_connection_success(self, fake_client):
        """returns self on success"""

        with patch.object(fake_client._client, "loop_start"), patch.object(
            fake_client._client, "connect_async"
        ):
            fake_client._client._state = paho.mqtt_cs_connected
            with fake_client as x:
                assert fake_client == x

    def test_assert_message_published(self, fake_client):
        """If it couldn't immediately publish the message, error out"""

        class FakeMessage:
            is_published = False
            rc = 1

        with patch.object(fake_client._client, "subscribe"), patch.object(
            fake_client._client, "publish", return_value=FakeMessage()
        ):
            with pytest.raises(exceptions.MQTTError):
                fake_client.publish("abc", "123")

    def test_assert_message_published_unknown_err(self, fake_client):
        """Same, but with an unknown error code"""

        class FakeMessage:
            is_published = False
            rc = 2342423

        with patch.object(fake_client._client, "subscribe"), patch.object(
            fake_client._client, "publish", return_value=FakeMessage()
        ):
            with pytest.raises(exceptions.MQTTError):
                fake_client.publish("abc", "123")


class TestTLS(object):
    def test_missing_cert_gives_error(self):
        """Missing TLS cert gives an error"""
        args = {"certfile": "/lcliueurhug/ropko3kork32"}

        with pytest.raises(exceptions.MQTTTLSError):
            _handle_tls_args(args)

    def test_disabled_tls(self):
        """Even if there are other invalid options, disable tls and early exit
        without checking other args
        """
        args = {"certfile": "/lcliueurhug/ropko3kork32", "enable": False}

        parsed_args = _handle_tls_args(args)
        assert not parsed_args

    def test_invalid_tls_ver(self):
        """Bad tls versions raise exception"""
        args = {"tls_version": "custom_tls"}

        with pytest.raises(exceptions.MQTTTLSError):
            _handle_tls_args(args)


@pytest.fixture(name="req")
def fix_example_request():
    spec = {"topic": "{request_topic:s}", "payload": "abc123"}

    return spec.copy()


class TestRequests:
    def test_unknown_fields(self, req, includes):
        """Unkown args should raise an error"""
        req["fodokfowe"] = "Hello"

        with pytest.raises(exceptions.UnexpectedKeysError):
            MQTTRequest(Mock(), req, includes)

    def test_missing_format(self, req, includes):
        """All format variables should be present"""
        del includes.variables["request_topic"]

        with pytest.raises(exceptions.MissingFormatError):
            MQTTRequest(Mock(), req, includes)

    def test_correct_format(self, req, includes):
        """All format variables should be present"""
        MQTTRequest(Mock(), req, includes)


class TestSubscription(object):
    @staticmethod
    def get_mock_client_with(subcribe_action):
        mock_paho = Mock(spec=paho.Client, subscribe=subcribe_action)
        mock_client = Mock(
            spec=MQTTClient,
            _client=mock_paho,
            _subscribed={},
            _subscribe_lock=MagicMock(),
        )
        return mock_client

    def test_handles_subscriptions(self):
        def subscribe_success(topic, *args, **kwargs):
            return (0, 123)

        mock_client = TestSubscription.get_mock_client_with(subscribe_success)

        MQTTClient.subscribe(mock_client, "abc")

        assert mock_client._subscribed[123].topic == "abc"
        assert mock_client._subscribed[123].subscribed == False

    def test_no_subscribe_on_err(self):
        def subscribe_err(topic, *args, **kwargs):
            return (1, 123)

        mock_client = TestSubscription.get_mock_client_with(subscribe_err)

        MQTTClient.subscribe(mock_client, "abc")

        assert mock_client._subscribed == {}

    def test_no_subscribe_on_unrecognised_suback(self):
        def subscribe_success(topic, *args, **kwargs):
            return (0, 123)

        mock_client = TestSubscription.get_mock_client_with(subscribe_success)

        MQTTClient._on_subscribe(mock_client, "abc", {}, 123, 0)

        assert mock_client._subscribed == {}
