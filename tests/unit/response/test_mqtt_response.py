import random
import re
import threading
from unittest.mock import Mock, patch

import pytest

from tavern._core import exceptions
from tavern._core.loader import ANYTHING
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


class TestResponse:
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

        msg_lock = threading.RLock()

        responses: dict[str, list[FakeMessage]] = {
            message.topic: [] for message in fake_messages
        }
        for message in fake_messages:
            responses[message.topic].append(message)

        def yield_all_messages():
            def inner(topic, timeout):
                try:
                    msg_lock.acquire()

                    r = responses[topic]
                    if len(r) == 0:
                        return None

                    return r.pop(random.randint(0, len(r) - 1))
                finally:
                    msg_lock.release()

            return inner

        fake_client = Mock(
            spec=MQTTClient,
            message_received=yield_all_messages(),
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

    @pytest.mark.parametrize("n_messages", (1, 2))
    def test_ext_function_called_save(self, includes, n_messages: int):
        """Make sure that it calls ext functions appropriately on individual MQTT
        responses and saved the response"""
        expecteds = []
        fake_messages = []
        for i in range(n_messages):
            expected = {
                "topic": f"/a/b/c/{i + 1}",
                "payload": "hello",
                "save": {
                    "$ext": {"function": f"function_name_{i + 1}"},
                },
            }

            fake_message = FakeMessage(expected)

            expecteds += [expected]
            fake_messages += [fake_message]

        verifier = self._get_fake_verifier(expecteds, fake_messages, includes)

        def fake_get_wrapped_response():
            def wrap(ext):
                def actual(response, *args, **kwargs):
                    match = re.match(r"function_name_(?P<idx>\d+)", ext["function"])
                    assert match
                    message_number = match.group("idx")
                    return {f"saved_topic_{message_number}": response.topic}

                return actual

            return wrap

        with patch(
            "tavern.response.get_wrapped_response_function",
            new_callable=fake_get_wrapped_response,
        ):
            saved = verifier.verify(None)

        assert len(verifier.received_messages) == n_messages

        for i in range(n_messages):
            assert verifier.received_messages[i].topic == fake_messages[i].topic

            assert len(saved) == n_messages

            assert saved[f"saved_topic_{i + 1}"] == expecteds[i]["topic"]

    def test_correct_message_eventually(self, includes):
        """One wrong messge, then the correct one"""

        expected = {"topic": "/a/b/c", "payload": "hello"}

        fake_message_good = FakeMessage(expected)
        fake_message_bad = FakeMessage({"topic": "/a/b/c", "payload": "goodbye"})

        verifier = self._get_fake_verifier(
            expected, [fake_message_bad, fake_message_good], includes
        )

        verifier.verify(expected)

        assert len(verifier.received_messages) >= 1
        received_topics = [m.topic for m in verifier.received_messages]
        assert fake_message_good.topic in received_topics

    def test_unexpected_fail(self, includes):
        """Messages marked unexpected fail test"""

        expected = {"topic": "/a/b/c", "payload": "hello", "unexpected": True}

        fake_message = FakeMessage(expected)

        verifier = self._get_fake_verifier(expected, [fake_message], includes)

        with pytest.raises(exceptions.TestFailError):
            verifier.verify(expected)

        assert len(verifier.received_messages) == 1
        assert verifier.received_messages[0].topic == fake_message.topic

    @pytest.mark.parametrize("r", range(10))
    def test_multiple_messages(self, includes, r):
        """One wrong message, two correct ones"""

        expected = [
            {"topic": "/a/b/c", "payload": "hello"},
            {"topic": "/d/e/f", "payload": "hellog"},
        ]

        fake_message_good_1 = FakeMessage(expected[0])
        fake_message_good_2 = FakeMessage(expected[1])
        fake_message_bad = FakeMessage({"topic": "/a/b/c", "payload": "goodbye"})

        messages = [fake_message_bad, fake_message_good_1, fake_message_good_2]
        random.shuffle(messages)

        verifier = self._get_fake_verifier(
            expected,
            messages,
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
            {"topic": "/d/e/f", "payload": "hellog"},
        ]

        fake_message_good_1 = FakeMessage(expected[0])
        fake_message_good_2 = FakeMessage(expected[1])

        messages = [fake_message_good_2, fake_message_good_1]
        random.shuffle(messages)

        verifier = self._get_fake_verifier(expected, messages, includes)

        verifier.verify(expected)

        assert len(verifier.received_messages) == 2
        received_topics = [m.topic for m in verifier.received_messages]
        assert fake_message_good_1.topic in received_topics
        assert fake_message_good_2.topic in received_topics

    # FIXME: Add tests for 'ext' functions are called in the right order

    @pytest.mark.parametrize(
        "payload",
        (
            (
                "!anything",
                ANYTHING,
            ),
            (
                "null",
                None,
            ),
            (
                "goog",
                "goog",
            ),
        ),
    )
    @pytest.mark.parametrize("r", range(10))
    def test_same_topic(self, includes, r, payload):
        """Messages coming in a different order"""

        expected = [
            {"topic": "/a/b/c", "payload": "hello"},
            {"topic": "/a/b/c", "payload": payload[0]},
        ]

        fake_message_good_1 = FakeMessage(expected[0])
        fake_message_good_2 = FakeMessage(expected[1])

        messages = [fake_message_good_2, fake_message_good_1]
        random.shuffle(messages)

        verifier = self._get_fake_verifier(expected, messages, includes)

        loaded = [
            {"topic": "/a/b/c", "payload": "hello"},
            {"topic": "/a/b/c", "payload": payload[1]},
        ]
        verifier.verify(loaded)

        assert len(verifier.received_messages) == 2
        received_topics = [m.topic for m in verifier.received_messages]
        assert fake_message_good_1.topic in received_topics
        assert fake_message_good_2.topic in received_topics
