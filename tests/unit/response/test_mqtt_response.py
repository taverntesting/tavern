import pytest
from mock import Mock

from tavern._plugins.mqtt.client import MQTTClient
from tavern.util import exceptions
from tavern._plugins.mqtt.response import MQTTResponse



def test_nothing_returned_fails():
    """Raises an error if no message was received"""
    fake_client = Mock(
        spec=MQTTClient,
        message_received=Mock(return_value=None),
    )

    expected = {
        "topic": "/a/b/c",
        "payload": "hello",
    }

    verifier = MQTTResponse(fake_client, "Test stage", expected, {})

    with pytest.raises(exceptions.TestFailError):
        verifier.verify(expected)

    assert not verifier.received_messages


class FakeMessage:
    def __init__(self, returned):
        self.topic = returned["topic"]
        self.payload = returned["payload"].encode("utf8")


class TestResponse(object):

    def _get_fake_verifier(self, expected, fake_messages):
        """Given a list of messages, return a mocked version of the MQTT
        response verifier which will take messages off the front of this list as
        if they were published

        This mocks it as if all messages were returned in order, which they
        might not have been...?
        """
        if not isinstance(fake_messages, list):
            pytest.fail("Need to pass a list of messages")

        def yield_all_messages():
            msg_copy = fake_messages[:]

            def inner(timeout):
                try:
                    return msg_copy.pop(0)
                except IndexError:
                    return None

            return inner

        fake_client = Mock(
            spec=MQTTClient,
            message_received=yield_all_messages(),
        )

        return MQTTResponse(fake_client, "Test stage", expected, {})

    def test_message_on_same_topic_fails(self):
        """Correct topic, wrong message"""

        expected = {
            "topic": "/a/b/c",
            "payload": "hello",
        }

        fake_message = FakeMessage({
            "topic": "/a/b/c",
            "payload": "goodbye",
        })

        verifier = self._get_fake_verifier(expected, [fake_message])

        with pytest.raises(exceptions.TestFailError):
            verifier.verify(expected)

        assert len(verifier.received_messages) == 1
        assert verifier.received_messages[0].topic == fake_message.topic

    def test_correct_message(self):
        """Both correct matches"""

        expected = {
            "topic": "/a/b/c",
            "payload": "hello",
        }

        fake_message = FakeMessage(expected)

        verifier = self._get_fake_verifier(expected, [fake_message])

        verifier.verify(expected)

        assert len(verifier.received_messages) == 1
        assert verifier.received_messages[0].topic == fake_message.topic

    def test_correct_message_eventually(self):
        """One wrong messge, then the correct one"""

        expected = {
            "topic": "/a/b/c",
            "payload": "hello",
        }

        fake_message_good = FakeMessage(expected)
        fake_message_bad = FakeMessage({
            "topic": "/a/b/c",
            "payload": "goodbye",
        })

        verifier = self._get_fake_verifier(expected, [fake_message_bad, fake_message_good])

        verifier.verify(expected)

        assert len(verifier.received_messages) == 2
        assert verifier.received_messages[0].topic == fake_message_bad.topic
        assert verifier.received_messages[1].topic == fake_message_good.topic
