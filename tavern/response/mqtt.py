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

        etopic = self.expected["topic"]
        epayload = self.expected["payload"]

        received = self._client.message_received(**self.expected)

        logger.debug(received)

        if not received:
            self._adderr("Expected '%s' on topic '%s' but no such message received",
                epayload, etopic)

        if self.errors:
            raise TestFailError("Test '{:s}' failed:\n{:s}".format(self.name, self._str_errors()))

        return {}
