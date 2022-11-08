import concurrent
import concurrent.futures
import itertools
import json
import logging
import time

from tavern._core import exceptions
from tavern._core.dict_util import check_keys_match_recursive
from tavern._core.loader import ANYTHING
from tavern._core.pytest.newhooks import call_hook
from tavern._core.report import attach_yaml
from tavern.response import BaseResponse
from .client import MQTTClient

logger = logging.getLogger(__name__)

_default_timeout = 1


class MQTTResponse(BaseResponse):
    def __init__(self, client: MQTTClient, name, expected, test_block_config):
        super().__init__(name, expected, test_block_config)

        self._client = client

        self.received_messages = []  # type: ignore

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

        try:
            return self._await_response()
        finally:
            self._client.unsubscribe_all()

    def _await_response(self):
        """Actually wait for response"""

        # pylint: disable=too-many-statements

        indexed = [(i, v) for i, v in
                   enumerate(self.expected["mqtt_responses"])]

        by_topic = {
            m: list(v) for m, v in
            itertools.groupby(indexed,
                              lambda x: x[1]["topic"])
        }
        logger.error(by_topic)

        correct_messages = []
        warnings = []

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = []

            for topic, (_, v) in by_topic.items():
                logger.error("topic:%s", topic)
                logger.error("v:%s", v)
                logger.debug("Starting thread for %s", topic)
                futures.append(
                    executor.submit(self._await_specific_message, topic, v))

            for future in concurrent.futures.as_completed(futures):
                # for future in futures:
                try:
                    msg, warnings = future.result()
                except Exception as e:
                    raise exceptions.ConcurrentError(
                        "unexpected error getting result from future"
                    ) from e
                else:
                    warnings.extend(warnings)
                    correct_messages.append(msg)

        if self.errors:
            if warnings:
                self._adderr("\n".join(warnings))

            raise exceptions.TestFailError(
                "Test '{:s}' failed:\n{:s}".format(self.name,
                                                   self._str_errors()),
                failures=self.errors,
            )

        saved = {}

        for idx, msg in enumerate(correct_messages):
            saved.update(
                self.maybe_get_save_values_from_save_block("json", msg.payload)
            )
            saved.update(
                self.maybe_get_save_values_from_ext(msg, expected[idx]))

        return saved

    def _await_specific_message(self, topic, expected):
        """
        Waits for the specific message

        Args:
            expected (list): expected response for this block

        Returns:
            tuple(msg, list): The correct message (if any) and warnings from processing the message
        """
        # pylint: disable=too-many-statements

        timeout = max(m.get("timeout", _default_timeout) for m in expected)
        logger.error(timeout)

        test_strictness = self.test_block_config.strict
        block_strictness = test_strictness.setting_for("json")

        time_spent = 0
        msg = None
        while time_spent < timeout:
            t0 = time.time()

            msg = self._client.message_received(timeout - time_spent)

            if not msg:
                # timed out
                break

            if msg.topic != topic:
                # If the message wasn't on the topic expected by this thread, put it back in the queue. This ensures
                # that it will be eventually process by something else. TODO: This might cause high CPU usage if it's
                # spinning waiting for a specific message to arrive but there's some other message that was
                # published that the client is also listening to. In reality, that other thread should pick up the
                # message from the queue and dtermine whether it's right or not. Needs more testing?
                self._client.message_ignore(msg)
                continue

            call_hook(
                self.test_block_config,
                "pytest_tavern_beta_after_every_response",
                expected=expected,
                response=msg,
            )

            self.received_messages.append(msg)

            msg.payload = msg.payload.decode("utf8")

            attach_yaml(
                {
                    "topic": msg.topic,
                    "payload": msg.payload,
                    "timestamp": msg.timestamp,
                },
                name="rest_response",
            )

            msg = None
            time_spent += time.time() - t0

        if msg:
            if expected.get("unexpected"):
                self._adderr(
                    "Got '%s' on topic '%s' marked as unexpected",
                    expected_payload,
                    topic,
                )

            self._maybe_run_validate_functions(msg)
        else:
            self._adderr(
                "Expected '%s' on topic '%s' but no such message received",
                expected_payload,
                topic,
            )

        return msg, warnings


class _MessageVerifier:
    def __init__(self, timeout, expected):
        self.expires = time.time() + timeout

        self.expected_payload, self.expect_json_payload = self._get_payload_vals(
            expected)

    def is_valid(self, msg):
        if time.time() > self.expires:
            return False

        # Any warnings to do with the request
        # eg, if a message was received but it didn't match, message had payload, etc.
        warnings = []

        def addwarning(w, *args, **kwargs):
            logger.warning(w, *args, **kwargs)
            warnings.append(w % args)

        if self.expect_json_payload:
            try:
                msg.payload = json.loads(msg.payload)
            except json.decoder.JSONDecodeError:
                addwarning(
                    "Expected a json payload but got '%s'",
                    msg.payload,
                    exc_info=True,
                )
                return False

        if self.expected_payload is None:
            # pylint: disable=no-else-break
            if msg.payload is None or msg.payload == "":
                logger.info(
                    "Got message with no payload (as expected) on '%s'",
                    topic
                )
                break
            else:
                addwarning(
                    "Message had payload '%s' but we expected no payload",
                    msg.payload,
                )
        elif self.expected_payload is ANYTHING:
            logger.info("Got message on %s matching !anything token", topic)
            break
        elif msg.payload != self.expected_payload:
            if self.expect_json_payload:
                try:
                    check_keys_match_recursive(
                        self.expected_payload, msg.payload, [],
                        strict=block_strictness
                    )
                except exceptions.KeyMismatchError:
                    # Just want to log the mismatch
                    pass
                else:
                    logger.info(
                        "Got expected message in '%s' with expected payload",
                        msg.topic,
                    )
                    logger.debug("Matched payload was '%s", msg.payload)
                    break

            addwarning(
                "Got unexpected payload on topic '%s': '%s' (expected '%s')",
                msg.topic,
                msg.payload,
                self.expected_payload,
            )
        elif msg.topic != topic:
            addwarning(
                "Got unexpected message in '%s' with payload '%s'",
                msg.topic,
                msg.payload,
            )
        else:
            logger.info(
                "Got expected message in '%s' with expected payload",
                msg.topic,
            )
            logger.debug("Matched payload was '%s", msg.payload)
            break


@staticmethod


def _get_payload_vals(expected):
    # TODO move this check to initialisation/schema checking
    if "json" in expected:
        if "payload" in expected:
            raise exceptions.BadSchemaError(
                "Can only specify one of 'payload' or 'json' in MQTT response"
            )

        payload = expected["json"]
        json_payload = True

        if payload.pop("$ext", None):
            raise exceptions.InvalidExtBlockException(
                "json",
            )
    elif "payload" in expected:
        payload = expected["payload"]
        json_payload = False
    else:
        payload = None
        json_payload = False

    return payload, json_payload
