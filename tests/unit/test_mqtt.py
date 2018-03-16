import pytest
from mock import patch
import paho.mqtt.client as paho

from tavern.mqtt import MQTTClient
from tavern.util import exceptions


def test_host_required():
    """Always needs a host, but it's the only required key"""
    with pytest.raises(exceptions.MissingKeysError):
        MQTTClient()

    args = {
        "connect": {
            "host": "localhost",
        }
    }

    MQTTClient(**args)


class TestClient(object):

    @pytest.fixture(name="fake_client")
    def fix_fake_client(self):
        args = {
            "connect": {
                "host": "localhost",
            }
        }

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

        with patch.object(fake_client._client, "loop_start"), \
        patch.object(fake_client._client, "connect_async"):
            fake_client._client._state = paho.mqtt_cs_connected
            with fake_client as x:
                assert fake_client == x

    def test_assert_message_published(self, fake_client):
        """If it couldn't immediately publish the message, error out"""

        class FakeMessage:
            is_published = False
            rc = 1

        with patch.object(fake_client._client, "subscribe"), \
        patch.object(fake_client._client, "publish", return_value=FakeMessage()):
            with pytest.raises(exceptions.MQTTError):
                fake_client.publish("abc", "123")

    def test_assert_message_published_unknown_err(self, fake_client):
        """Same, but with an unknown error code"""

        class FakeMessage:
            is_published = False
            rc = 2342423

        with patch.object(fake_client._client, "subscribe"), \
        patch.object(fake_client._client, "publish", return_value=FakeMessage()):
            with pytest.raises(exceptions.MQTTError):
                fake_client.publish("abc", "123")


class TestTLS(object):

    def test_disabled_tls(self):
        """Even if there are other invalid options, disable tls and early exit
        without checking other args
        """
        args = {
            "connect": {
                "host": "localhost",
            },
            "tls": {
                "certfile": "/lcliueurhug/ropko3kork32",
            }
        }

        with pytest.raises(exceptions.MQTTTLSError):
            MQTTClient(**args)

        args["tls"]["enable"] = False

        c = MQTTClient(**args)
        assert not c._enable_tls

    def test_invalid_tls_ver(self):
        """Bad tls versions raise exception
        """
        args = {
            "connect": {
                "host": "localhost",
            },
            "tls": {
                "tls_version": "custom_tls",
            }
        }

        with pytest.raises(exceptions.MQTTTLSError):
            MQTTClient(**args)
