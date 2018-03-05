import logging
import json
import time

from tavern.schemas.extensions import get_wrapped_response_function
from tavern.util import exceptions
from .base import BaseResponse

try:
    LoadException = json.decoder.JSONDecodeError
except AttributeError:
    # python 2 raises ValueError on json loads() error instead
    LoadException = ValueError

logger = logging.getLogger(__name__)


class MQTTResponse(BaseResponse):

    def __init__(self, client, name, expected, test_block_config):
        # pylint: disable=unused-argument

        super(MQTTResponse, self).__init__()

        self.name = name

        payload = expected.get("payload")

        self.validate_function = None
        if isinstance(payload, dict):
            if "$ext" in payload:
                self.validate_function = get_wrapped_response_function(payload["$ext"])

        self.expected = expected
        self.response = None

        self._client = client

        self.received_messages = []

    def __str__(self):
        if self.response:
            return self.response.payload
        else:
            return "<Not run yet>"

    def verify(self, response):
        """Ensure mqtt message has arrived

        Args:
            response: not used
        """

        self.response = response

        topic = self.expected["topic"]
        timeout = self.expected.get("timeout", 1)

        # TODO move this check to initialisation/schema checking
        if "json" in self.expected:
            if "payload" in self.expected:
                raise exceptions.BadSchemaError("Can only specify one of 'payload' or 'json' in MQTT response")

            payload = self.expected["json"]
            json_payload = True
        else:
            payload = self.expected["payload"]
            json_payload = False

        time_spent = 0

        while time_spent < timeout:
            t0 = time.time()

            msg = self._client.message_received(timeout - time_spent)

            if not msg:
                # timed out
                break

            self.received_messages.append(msg)

            msg.payload = msg.payload.decode("utf8")

            if json_payload:
                try:
                    msg.payload = json.loads(msg.payload)
                except LoadException:
                    logger.warning("Expected a json payload but got '%s'", msg.payload)
                    msg = None
                    continue

            if msg.payload != payload:
                logger.warning("Got unexpected payload on topic '%s': '%s' (expected '%s')",
                    msg.topic, msg.payload, payload)
            elif msg.topic != topic:
                logger.warning("Got unexpected message in '%s' with payload '%s'",
                    msg.topic, msg.payload)
            else:
                logger.info("Got expected message in '%s' with payload '%s'",
                    msg.topic, msg.payload)
                break

            msg = None
            time_spent += time.time() - t0

        if not msg:
            self._adderr("Expected '%s' on topic '%s' but no such message received",
                payload, topic)

        if self.errors:
            raise exceptions.TestFailError("Test '{:s}' failed:\n{:s}".format(
                self.name, self._str_errors()))

        return {}
