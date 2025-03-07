import concurrent
import concurrent.futures
import contextlib
import itertools
import json
import logging
import time
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Optional, Union

from paho.mqtt.client import MQTTMessage

from tavern._core import exceptions
from tavern._core.dict_util import check_keys_match_recursive
from tavern._core.loader import ANYTHING
from tavern._core.pytest.config import TestConfig
from tavern._core.pytest.newhooks import call_hook
from tavern._core.report import attach_yaml
from tavern._core.strict_util import StrictOption
from tavern.response import BaseResponse

from .client import MQTTClient

logger: logging.Logger = logging.getLogger(__name__)

_default_timeout = 1


class MQTTResponse(BaseResponse):
    response: MQTTMessage

    def __init__(
        self,
        client: MQTTClient,
        name: str,
        expected: TestConfig,
        test_block_config: TestConfig,
    ) -> None:
        super().__init__(name, expected, test_block_config)

        self._client = client

        self.received_messages: list = []

    def __str__(self) -> str:
        if self.response:
            return self.response.payload.decode("utf-8")
        else:
            return "<Not run yet>"

    def verify(self, response: MQTTMessage) -> Mapping:
        """Ensure mqtt message has arrived

        Args:
            response: not used except for debug printing
        """

        self.response = response

        try:
            return self._await_response()
        finally:
            self._client.unsubscribe_all()

    def _await_response(self) -> Mapping:
        """Actually wait for response

        Returns:
            things to save to variables for the rest of this test
        """

        # Get into class with metadata attached
        expected = self.expected["mqtt_responses"]

        by_topic = {
            m: list(v) for m, v in itertools.groupby(expected, lambda x: x["topic"])
        }

        correct_messages: list[_ReturnedMessage] = []
        warnings: list[str] = []

        with concurrent.futures.ThreadPoolExecutor() as executor:
            futures = []

            for topic, expected_for_topic in by_topic.items():
                logger.debug("Starting thread for messages on topic '%s'", topic)
                futures.append(
                    executor.submit(
                        self._await_messages_on_topic, topic, expected_for_topic
                    )
                )

            for future in concurrent.futures.as_completed(futures):
                # for future in futures:
                try:
                    messages, warnings = future.result()
                except Exception as e:
                    raise exceptions.ConcurrentError(
                        "unexpected error getting result from future"
                    ) from e
                else:
                    warnings.extend(warnings)
                    correct_messages.extend(messages)

        if self.errors:
            if warnings:
                self._adderr("\n".join(warnings))

            raise exceptions.TestFailError(
                f"Test '{self.name:s}' failed:\n{self._str_errors():s}",
                failures=self.errors,
            )

        saved: dict = {}

        for msg in correct_messages:
            # Check saving things from the payload and from json
            saved.update(
                self.maybe_get_save_values_from_save_block(
                    "payload",
                    msg.msg.payload,
                    outer_save_block=msg.expected,
                )
            )
            saved.update(
                self.maybe_get_save_values_from_save_block(
                    "json",
                    msg.msg.payload,
                    outer_save_block=msg.expected,
                )
            )

            saved.update(self.maybe_get_save_values_from_ext(msg.msg, msg.expected))

        # Trying to save might have introduced errors, so check again
        if self.errors:
            raise exceptions.TestFailError(
                f"Saving results from test '{self.name:s}' failed:\n{self._str_errors():s}",
                failures=self.errors,
            )

        return saved

    def _await_messages_on_topic(
        self, topic: str, expected: list[dict]
    ) -> tuple[list["_ReturnedMessage"], list[str]]:
        """
        Waits for the specific message

        Args:
            topic: topic to listen on
            expected: expected response for this block

        Returns:
            The correct message (if any) and warnings from processing the message
        """

        timeout = max(m.get("timeout", _default_timeout) for m in expected)

        # A list of verifiers that can be used to validate messages for this topic
        verifiers = [_MessageVerifier(self.test_block_config, v) for v in expected]

        correct_messages = []
        warnings = []

        time_spent = 0.0
        while (time_spent < timeout) and verifiers:
            t0 = time.time()

            msg = self._client.message_received(topic, timeout - time_spent)

            if not msg:
                # timed out
                break

            logger.debug("Seeing if message '%s' matched expected", msg)

            call_hook(
                self.test_block_config,
                "pytest_tavern_beta_after_every_response",
                expected=expected,
                response=msg,
            )

            self.received_messages.append(msg)

            with contextlib.suppress(AttributeError):
                msg.payload = msg.payload.decode("utf8")

            attach_yaml(
                {
                    "topic": msg.topic,
                    "payload": msg.payload,
                    "timestamp": msg.timestamp,
                },
                name="rest_response",
            )

            found: list[int] = []
            for i, v in enumerate(verifiers):
                if v.is_valid(msg):
                    correct_messages.append(_ReturnedMessage(v.expected, msg))
                    if found:
                        logger.warning(
                            "Message was matched by multiple mqtt_response blocks"
                        )
                    found.append(i)
                warnings.extend(v.popwarnings())
            verifiers = [v for (i, v) in enumerate(verifiers) if i not in found]

            time_spent += time.time() - t0

        if verifiers:
            for v in verifiers:
                self._adderr(
                    "Expected '%s' on topic '%s' but no such message received",
                    v.expected_payload,
                    topic,
                )

        for msg in correct_messages:
            if msg.expected.get("unexpected"):
                self._adderr(
                    "Got '%s' on topic '%s' marked as unexpected",
                    msg.expected["payload"],
                    topic,
                )

            self._maybe_run_validate_functions(msg)

        return correct_messages, warnings


@dataclass
class _ReturnedMessage:
    """An actual message returned from the API and it's matching 'expected' block."""

    expected: Mapping
    msg: MQTTMessage


class _MessageVerifier:
    def __init__(self, test_block_config: TestConfig, expected: Mapping) -> None:
        self.expires = time.time() + expected.get("timeout", _default_timeout)

        self.expected = expected
        self.expected_payload, self.expect_json_payload = self._get_payload_vals(
            expected
        )

        test_strictness = test_block_config.strict
        self.block_strictness: StrictOption = test_strictness.option_for("json")

        # Any warnings to do with the request
        # eg, if a message was received but it didn't match, message had payload, etc.
        self.warnings: list[str] = []

    def is_valid(self, msg: MQTTMessage) -> bool:
        if time.time() > self.expires:
            return False

        topic = self.expected["topic"]

        def addwarning(w, *args, **kwargs):
            logger.warning(w, *args, **kwargs)
            self.warnings.append(w % args)

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
            if msg.payload is None or msg.payload == "":
                logger.info("Got message with no payload (as expected) on '%s'", topic)
                return True
            else:
                addwarning(
                    "Message had payload '%s' but we expected no payload",
                    msg.payload,
                )
        elif self.expected_payload is ANYTHING:
            logger.info("Got message on %s matching !anything token", topic)
            return True
        elif msg.payload != self.expected_payload:
            if self.expect_json_payload:
                try:
                    check_keys_match_recursive(
                        self.expected_payload,
                        msg.payload,
                        [],
                        strict=self.block_strictness,
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
                    return True

            addwarning(
                "Got unexpected payload on topic '%s': '%s' (expected '%s')",
                msg.topic,
                msg.payload,
                self.expected_payload,
            )
        else:
            logger.info(
                "Got expected message in '%s' with expected payload",
                msg.topic,
            )
            logger.debug("Matched payload was '%s", msg.payload)
            return True

        return False

    @staticmethod
    def _get_payload_vals(expected: Mapping) -> tuple[Optional[Union[str, dict]], bool]:
        """Gets the payload from the 'expected' block

        Returns:
            First element is the expected payload, second element is whether it's
                expected to be json or not
        """
        # TODO move this check to initialisation/schema checking
        if "json" in expected:
            if "payload" in expected:
                raise exceptions.BadSchemaError(
                    "Can only specify one of 'payload' or 'json' in MQTT response"
                )

            payload = expected["json"]
            json_payload = True

            if payload.pop("$ext", None):
                raise exceptions.MisplacedExtBlockException(
                    "json",
                )
        elif "payload" in expected:
            payload = expected["payload"]
            json_payload = False
        else:
            payload = None
            json_payload = False

        return payload, json_payload

    def popwarnings(self) -> list[str]:
        popped = []
        while self.warnings:
            popped.append(self.warnings.pop(0))
        return popped
