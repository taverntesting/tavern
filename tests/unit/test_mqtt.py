import time
from unittest.mock import MagicMock, Mock, patch

import paho.mqtt.client as paho
import pytest

from tavern._core import exceptions
from tavern._plugins.mqtt.client import MQTTClient, _handle_tls_args, _Subscription
from tavern._plugins.mqtt.request import MQTTRequest


def test_host_required():
    """Always needs a host, but it's the only required key"""
    with pytest.raises(exceptions.MissingKeysError):
        MQTTClient()

    args = {"connect": {"host": "localhost"}}

    MQTTClient(**args)


@pytest.fixture(name="fake_client")
def fix_fake_client():
    args = {"connect": {"host": "localhost", "timeout": 0.6}}

    mqtt_client = MQTTClient(**args)

    mqtt_client._subscribed[2] = _Subscription("abc")
    mqtt_client._subscription_mappings["abc"] = 2

    return mqtt_client


class TestClient:
    def test_no_queue(self, fake_client):
        """Trying to fetch from a nonexistent queue raised exception"""

        with pytest.raises(exceptions.MQTTTopicException):
            fake_client.message_received("", 0)

    def test_no_message(self, fake_client):
        """No message in queue returns None"""

        assert fake_client.message_received("abc", 0) is None

    def test_message_queued(self, fake_client):
        """Returns message in queue"""

        message = "abc123"

        fake_client._userdata["_subscribed"][2].queue.put(message)
        assert fake_client.message_received("abc", 0) == message

    def test_context_connection_failure(self, fake_client):
        """Unable to connect on __enter__ raises MQTTError"""

        fake_client._connect_timeout = 0.3

        with patch.object(fake_client._client, "loop_start"):
            with pytest.raises(exceptions.MQTTError):
                with fake_client:
                    pass

    def test_context_connection_success(self, fake_client):
        """returns self on success"""

        with (
            patch.object(fake_client._client, "loop_start"),
            patch.object(fake_client._client, "connect_async"),
        ):
            fake_client._client._state = paho.mqtt_cs_connected
            with fake_client as x:
                assert fake_client == x

    def test_assert_message_published_error(self, fake_client):
        """Error waiting for it to publish"""

        class FakeMessage(paho.MQTTMessageInfo):
            def wait_for_publish(self, timeout=None):
                raise RuntimeError

            rc = 1

        with (
            patch.object(fake_client._client, "subscribe"),
            patch.object(fake_client._client, "publish", return_value=FakeMessage(10)),
        ):
            with pytest.raises(exceptions.MQTTError):
                fake_client.publish("abc", "123")

    def test_assert_message_published_failure(self, fake_client: MQTTClient):
        """If it couldn't publish the message, error out"""

        class FakeMessage(paho.MQTTMessageInfo):
            def wait_for_publish(self, timeout=None):
                return

            def is_published(self):
                return False

            rc = 1

        with (
            patch.object(fake_client._client, "subscribe"),
            patch.object(fake_client._client, "publish", return_value=FakeMessage(10)),
        ):
            with pytest.raises(exceptions.MQTTError):
                fake_client.publish("abc", "123")

    def test_assert_message_published_delay(self, fake_client):
        """Published but only after a small delay"""

        class FakeMessage(paho.MQTTMessageInfo):
            def wait_for_publish(self, timeout=None):
                time.sleep(0.5)

            def is_published(self):
                return True

            rc = 1

        with (
            patch.object(fake_client._client, "subscribe"),
            patch.object(fake_client._client, "publish", return_value=FakeMessage(10)),
        ):
            fake_client.publish("abc", "123")

    def test_assert_message_published_unknown_err(self, fake_client):
        """Same, but with an unknown error code"""

        class FakeMessage(paho.MQTTMessageInfo):
            def is_published(self):
                return False

            rc = 2342423

        with (
            patch.object(fake_client._client, "subscribe"),
            patch.object(fake_client._client, "publish", return_value=FakeMessage(10)),
        ):
            with pytest.raises(exceptions.MQTTError):
                fake_client.publish("abc", "123")


class TestTLS:
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


class TestSubscription:
    @staticmethod
    def get_mock_client_with(subcribe_action):
        mock_paho = Mock(spec=paho.Client, subscribe=subcribe_action)
        mock_client = Mock(
            spec=MQTTClient,
            _client=mock_paho,
            _subscribed={},
            _subscription_mappings={},
            _subscribe_lock=MagicMock(),
        )
        return mock_client

    def test_handles_subscriptions(self):
        def subscribe_success(topic, *args, **kwargs):
            return (0, 123)

        mock_client = TestSubscription.get_mock_client_with(subscribe_success)

        MQTTClient.subscribe(mock_client, "abc")

        assert mock_client._subscribed[123].topic == "abc"
        assert mock_client._subscribed[123].subscribed is False

    def test_no_subscribe_on_err(self):
        def subscribe_err(topic, *args, **kwargs):
            return (1, 123)

        mock_client = TestSubscription.get_mock_client_with(subscribe_err)

        with pytest.raises(exceptions.MQTTError):
            MQTTClient.subscribe(mock_client, "abc")

        assert mock_client._subscribed == {}

    def test_no_subscribe_on_unrecognised_suback(self):
        def subscribe_success(topic, *args, **kwargs):
            return (0, 123)

        mock_client = TestSubscription.get_mock_client_with(subscribe_success)

        MQTTClient._on_subscribe(mock_client, "abc", {}, 123, 0)

        assert mock_client._subscribed == {}


class TestExtFunctions:
    @pytest.fixture()
    def basic_mqtt_request_args(self) -> dict:
        return {
            "topic": "/a/b/c",
        }

    def test_basic(self, fake_client, basic_mqtt_request_args, includes):
        MQTTRequest(fake_client, basic_mqtt_request_args, includes)

    def test_ext_function_bad(self, fake_client, basic_mqtt_request_args, includes):
        basic_mqtt_request_args["json"] = {"$ext": "kk"}

        with pytest.raises(exceptions.InvalidExtFunctionError):
            MQTTRequest(fake_client, basic_mqtt_request_args, includes)

    def test_ext_function_good(self, fake_client, basic_mqtt_request_args, includes):
        basic_mqtt_request_args["json"] = {
            "$ext": {
                "function": "operator:add",
                "extra_args": (1, 2),
            }
        }

        m = MQTTRequest(fake_client, basic_mqtt_request_args, includes)

        assert "payload" in m._publish_args
        assert m._publish_args["payload"] == "3"


class TestSSLContext:
    def test_ciphers_set_correctly(self):
        """Test that ciphers are set correctly in SSL context"""
        args = {
            "connect": {"host": "localhost"},
            "ssl_context": {
                "certfile": "/path/to/certfile",
                "keyfile": "/path/to/keyfile",
                "ciphers": "ECDHE-RSA-AES256-GCM-SHA384",
            },
        }

        with (
            patch(
                "tavern._plugins.mqtt.client.ssl.create_default_context"
            ) as mock_create_context,
            patch("tavern._plugins.mqtt.client.check_file_exists"),
        ):
            mock_context = MagicMock()
            mock_create_context.return_value = mock_context

            _ = MQTTClient(**args)

            mock_context.set_ciphers.assert_called_once_with(
                "ECDHE-RSA-AES256-GCM-SHA384"
            )
