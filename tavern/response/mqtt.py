import logging

from tavern.schemas.extensions import get_wrapped_response_function
from tavern.util.exceptions import TestFailError
from .base import BaseResponse

logger = logging.getLogger(__name__)


class MQTTResponse(BaseResponse):

    def __init__(self, client, name, expected, test_block_config):
        # pylint: disable=unused-argument

        self.name = name

        payload = expected.get("payload")

        if "$ext" in payload:
            self.validate_function = get_wrapped_response_function(payload["$ext"])
        else:
            self.validate_function = None

        self.expected = expected
        self.response = None

        self._client = client

        super(MQTTResponse, self).__init__()

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
        payload = self.expected["payload"]
        timeout = response.get("timeout", 1)

        time_spent = 0

        while time_spent < timeout:
            msg = self._client.message_received(timeout - time_spent)

            if not msg:
                # timed out
                break

            logger.debug(msg)

            if msg.payload != payload:
                logger.warning("Got unexpected payload on topic '%s': '%s' (expected '%s')",
                    msg.topic, msg.payload, payload)
            elif msg.topic != topic:
                logger.warning("Got unexpected message in '%s' with payload '%s'",
                    msg.topic, msg.payload)
            else:
                logger.info("Got expected message in '%s' with payload '%s'",
                    msg.topic, msg.payload)

        if not msg:
            self._adderr("Expected '%s' on topic '%s' but no such message received",
                payload, topic)

        if self.errors:
            raise TestFailError("Test '{:s}' failed:\n{:s}".format(self.name, self._str_errors()))

        return {}
