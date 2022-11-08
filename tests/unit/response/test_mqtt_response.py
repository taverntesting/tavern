import random
import threading
from unittest.mock import Mock

import pytest

from tavern._core import exceptions
from tavern._core.strict_util import StrictLevel
from tavern._plugins.mqtt.client import MQTTClient
from tavern._plugins.mqtt.response import MQTTResponse


def test_nothing_returned_fails(includes):
    """Raises an error if no message was received"""
    fake_client = Mock(spec=MQTTClient, message_received=Mock(return_value=None))

    expected = {"mqtt_responses": [{"topic": "/a/b/c", "payload": "hello"}]}

    verifier = MQTTResponse(
        fake_client,
        "Test stage",
        expected,
        includes.with_strictness(StrictLevel.all_on()),
    )

    with pytest.raises(exceptions.TestFailError):
        verifier.verify(expected)

    assert not verifier.received_messages


class FakeMessage:
    def __init__(self, returned):
        self.topic = returned["topic"]
        self.payload = returned["payload"].encode("utf8")
        self.timestamp = 0


class TestResponse(object):
    @staticmethod
    def _get_fake_verifier(expected, fake_messages, includes):
        """Given a list of messages, return a mocked version of the MQTT
        response verifier which will take messages off the front of this list as
        if they were published

        This mocks it as if all messages were returned in order, which they
        might not have been...?
        """
        if not isinstance(fake_messages, list):
            pytest.fail("Need to pass a list of messages")

        msg_copy = fake_messages[:]

        def replace_message(msg):
            msg_copy.append(msg)

        msg_lock = threading.RLock()

        def yield_all_messages():
            def inner(timeout):
                try:
                    msg_lock.acquire()
                    if len(msg_copy) == 0:
                        return None

                    return msg_copy.pop(random.randint(0, len(msg_copy) - 1))
                finally:
                    msg_lock.release()

            return inner

        fake_client = Mock(
            spec=MQTTClient,
            message_received=yield_all_messages(),
            message_ignore=replace_message,
        )

        if not isinstance(expected, list):
            expected = [expected]

        return MQTTResponse(
            fake_client, "Test stage", {"mqtt_responses": expected}, includes
        )

    def test_message_on_same_topic_fails(self, includes):
        """Correct topic, wrong message"""

        expected = {"topic": "/a/b/c", "payload": "hello"}

        fake_message = FakeMessage({"topic": "/a/b/c", "payload": "goodbye"})

        verifier = self._get_fake_verifier(expected, [fake_message], includes)

        with pytest.raises(exceptions.TestFailError):
            verifier.verify(expected)

        assert len(verifier.received_messages) == 1
        assert verifier.received_messages[0].topic == fake_message.topic

    def test_correct_message(self, includes):
        """Both correct matches"""

        expected = {"topic": "/a/b/c", "payload": "hello"}

        fake_message = FakeMessage(expected)

        verifier = self._get_fake_verifier(expected, [fake_message], includes)

        verifier.verify(expected)

        assert len(verifier.received_messages) == 1
        assert verifier.received_messages[0].topic == fake_message.topic

    def test_correct_message_eventually(self, includes):
        """One wrong messge, then the correct one"""

        expected = {"topic": "/a/b/c", "payload": "hello"}

        fake_message_good = FakeMessage(expected)
        fake_message_bad = FakeMessage({"topic": "/a/b/c", "payload": "goodbye"})

        verifier = self._get_fake_verifier(
            expected, [fake_message_bad, fake_message_good], includes
        )

        verifier.verify(expected)

        assert len(verifier.received_messages) == 2
        assert verifier.received_messages[0].topic == fake_message_bad.topic
        assert verifier.received_messages[1].topic == fake_message_good.topic

    @pytest.mark.parametrize("r", range(10))
    def test_multiple_messages(self, includes, r):
        """One wrong message, two correct ones"""

        expected = [
            {"topic": "/a/b/c", "payload": "hello"},
            {"topic": "/d/e/f", "payload": "hello"},
        ]

        fake_message_good_1 = FakeMessage(expected[0])
        fake_message_good_2 = FakeMessage(expected[1])
        fake_message_bad = FakeMessage({"topic": "/a/b/c", "payload": "goodbye"})

        verifier = self._get_fake_verifier(
            expected,
            [fake_message_bad, fake_message_good_1, fake_message_good_2],
            includes,
        )

        verifier.verify(expected)

        assert len(verifier.received_messages) >= 2
        received_topics = [m.topic for m in verifier.received_messages]
        assert fake_message_good_1.topic in received_topics
        assert fake_message_good_2.topic in received_topics

    @pytest.mark.parametrize("r", range(10))
    def test_different_order(self, includes, r):
        """Messages coming in a different order"""

        expected = [
            {"topic": "/a/b/c", "payload": "hello"},
            {"topic": "/d/e/f", "payload": "hello"},
        ]

        fake_message_good_1 = FakeMessage(expected[0])
        fake_message_good_2 = FakeMessage(expected[1])

        verifier = self._get_fake_verifier(
            expected, [fake_message_good_2, fake_message_good_1], includes
        )

        verifier.verify(expected)

        assert len(verifier.received_messages) >= 2
        received_topics = [m.topic for m in verifier.received_messages]
        assert fake_message_good_1.topic in received_topics
        assert fake_message_good_2.topic in received_topics

    def test_unexpected_fail(self, includes):
        """Messages marked unexpected fail test"""

        expected = {"topic": "/a/b/c", "payload": "hello", "unexpected": True}

        fake_message = FakeMessage(expected)

        verifier = self._get_fake_verifier(expected, [fake_message], includes)

        with pytest.raises(exceptions.TestFailError):
            verifier.verify(expected)

        assert len(verifier.received_messages) == 1
        assert verifier.received_messages[0].topic == fake_message.topic
