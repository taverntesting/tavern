import logging
import json
import time

from tavern.util import exceptions
from tavern.response.base import BaseResponse
from tavern.util.dict_util import check_keys_match_recursive
from tavern.util.loader import ANYTHING

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

        self._check_for_validate_functions(expected.get("payload", {}))

        self.expected = expected
        self.response = None

        self._client = client

        self.received_messages = []

    def __str__(self):
        if self.response:
            return self.response.payload
        else:
            return "<Not run yet>"

    def _get_payload_vals(self):
        # TODO move this check to initialisation/schema checking
        if "json" in self.expected:
            if "payload" in self.expected:
                raise exceptions.BadSchemaError(
                    "Can only specify one of 'payload' or 'json' in MQTT response"
                )

            payload = self.expected["json"]
            json_payload = True
        elif "payload" in self.expected:
            payload = self.expected["payload"]
            json_payload = False
        else:
            payload = None
            json_payload = False

        return payload, json_payload

    def _await_response(self):
        """Actually wait for response"""
        topic = self.expected["topic"]
        timeout = self.expected.get("timeout", 1)

        payload, json_payload = self._get_payload_vals()

        time_spent = 0

        msg = None

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
                    logger.warning(
                        "Expected a json payload but got '%s'",
                        msg.payload,
                        exc_info=True,
                    )
                    msg = None
                    continue

            if not payload:
                if not msg.payload:
                    logger.info(
                        "Got message with no payload (as expected) on '%s'", topic
                    )
                    break
                else:
                    logger.warning(
                        "Message had payload '%s' but we expected no payload"
                    )
            elif payload is ANYTHING:
                logger.info("Got message on %s matching !anything token", topic)
                break
            elif msg.payload != payload:
                if json_payload:
                    try:
                        check_keys_match_recursive(payload, msg.payload, [])
                    except exceptions.KeyMismatchError:
                        # Just want to log the mismatch
                        pass
                    else:
                        logger.info(
                            "Got expected message in '%s' with payload '%s'",
                            msg.topic,
                            msg.payload,
                        )
                        break

                logger.warning(
                    "Got unexpected payload on topic '%s': '%s' (expected '%s')",
                    msg.topic,
                    msg.payload,
                    payload,
                )
            elif msg.topic != topic:
                logger.warning(
                    "Got unexpected message in '%s' with payload '%s'",
                    msg.topic,
                    msg.payload,
                )
            else:
                logger.info(
                    "Got expected message in '%s' with payload '%s'",
                    msg.topic,
                    msg.payload,
                )
                break

            msg = None
            time_spent += time.time() - t0

        if not msg:
            self._adderr(
                "Expected '%s' on topic '%s' but no such message received",
                payload,
                topic,
            )

        if self.errors:
            raise exceptions.TestFailError(
                "Test '{:s}' failed:\n{:s}".format(self.name, self._str_errors()),
                failures=self.errors,
            )

        return {}

    def verify(self, response):
        """Ensure mqtt message has arrived

        Args:
            response: not used
        """

        self.response = response

        try:
            return self._await_response()
        finally:
            self._client.unsubscribe_all()
