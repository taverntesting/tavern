import logging
import time

try:
    from queue import Queue, Full, Empty
except ImportError:
    from Queue import Queue, Full, Empty

import paho.mqtt.client as paho

from .util.dict_util import check_expected_keys
from .util import exceptions


# MQTT error values
_err_vals = {
    -1: "MQTT_ERR_AGAIN",
    0: "MQTT_ERR_SUCCESS",
    1: "MQTT_ERR_NOMEM",
    2: "MQTT_ERR_PROTOCOL",
    3: "MQTT_ERR_INVAL",
    4: "MQTT_ERR_NO_CONN",
    5: "MQTT_ERR_CONN_REFUSED",
    6: "MQTT_ERR_NOT_FOUND",
    7: "MQTT_ERR_CONN_LOST",
    8: "MQTT_ERR_TLS",
    9: "MQTT_ERR_PAYLOAD_SIZE",
    10: "MQTT_ERR_NOT_SUPPORTED",
    11: "MQTT_ERR_AUTH",
    12: "MQTT_ERR_ACL_DENIED",
    13: "MQTT_ERR_UNKNOWN",
    14: "MQTT_ERR_ERRNO",
    15: "MQTT_ERR_QUEUE_SIZE",
}


logger = logging.getLogger(__name__)


class MQTTClient(object):
    # pylint: disable=too-many-instance-attributes

    def __init__(self, **kwargs):
        expected_blocks = {
            "client": {
                "client_id",
                "clean_session",
                # Can't really use this easily...
                # "userdata",
                # Force mqttv311 - fix if this becomes an issue
                # "protocol",
                "transport",
            },
            "connect": {
                "host",
                "port",
                "keepalive",
                "timeout",
            },
            "tls": {
                "enable",
                # TODO custom ca certs etc.
            },
            "auth": {
                "username",
                "password",
            },
        }

        # check main block first
        check_expected_keys(expected_blocks.keys(), kwargs)

        # then check constructor/connect/tls_set args
        self._client_args = kwargs.pop("client", {})
        check_expected_keys(expected_blocks["client"], self._client_args)

        self._connect_args = kwargs.pop("connect", {})
        check_expected_keys(expected_blocks["connect"], self._connect_args)

        self._auth_args = kwargs.pop("auth", {})
        check_expected_keys(expected_blocks["auth"], self._auth_args)

        if "host" not in self._connect_args:
            msg = "Need 'host' in 'connect' block for mqtt"
            logger.error(msg)
            raise exceptions.MissingKeysError(msg)

        self._connect_timeout = self._connect_args.pop("timeout", 3)

        # If there is any tls kwarg (including 'enable'), enable tls
        self._tls_args = kwargs.pop("tls", {})
        self._enable_tls = bool(self._tls_args)
        # don't want to pass this through to tls_set
        self._tls_args.pop("enable", None)

        logger.debug("Paho client args: %s", self._client_args)
        self._client = paho.Client(**self._client_args)
        self._client.enable_logger()

        if self._auth_args:
            self._client.username_pw_set(**self._auth_args)

        self._client.on_message = self._on_message

        if self._enable_tls:
            self._client.tls_set(**self._tls_args)

        # Arbitrary number, could just be 1 and only accept 1 message per stages
        # but we might want to raise an error if more than 1 message is received
        # during a test stage.
        self._message_queue = Queue(maxsize=10)
        self._userdata = {
            "queue": self._message_queue,
        }
        self._client.user_data_set(self._userdata)

    @staticmethod
    def _on_message(client, userdata, message):
        """Add any messages received to the queue

        Todo:
            If the queue is faull trigger an error in main thread somehow
        """
        # pylint: disable=unused-argument

        logger.info("Received mqtt message on %s", message.topic)

        try:
            userdata["queue"].put(message)
        except Full:
            logger.exception("message queue full")

    def message_received(self, timeout=1):
        """Check that a message is in the message queue

        Args:
            timeout (int): How long to wait before signalling that the message
                was not received.

        Returns:
            bool: whether the message was received within the timeout

        Todo:
            Allow regexes for topic names? Better validation for mqtt payloads
        """

        try:
            msg = self._message_queue.get(block=True, timeout=timeout)
        except Empty:
            logger.error("Message not received after %d seconds", timeout)
            return None
        else:
            return msg

    def publish(self, topic, payload, *args, **kwargs):
        """publish message using paho library
        """
        logger.debug("Publishing on '%s'", topic)

        msg = self._client.publish(topic, payload, *args, **kwargs)

        if not msg.is_published:
            raise exceptions.MQTTError("err {:s}: {:s}".format(_err_vals.get(msg.rc, "unknown"), paho.error_string(msg.rc)))

        return msg

    def subscribe(self, topic, *args, **kwargs):
        """Subcribe to topic

        should be called for every expected message in mqtt_response
        """
        logger.debug("subscribing to topic '%s'", topic)
        self._client.subscribe(topic, *args, **kwargs)

    def __enter__(self):
        self._client.connect_async(**self._connect_args)
        self._client.loop_start()

        elapsed = 0

        while elapsed < self._connect_timeout:
            # pylint: disable=protected-access
            if self._client._state == paho.mqtt_cs_connected:
                logger.debug("Connected to broker at %s", self._connect_args["host"])
                return self
            else:
                logger.debug("Not connected after %s seconds - waiting", elapsed)

            # TODO
            # configurable?
            time.sleep(0.25)
            elapsed += 0.25

        logger.error("Could not connect to broker after %s seconds", self._connect_timeout)
        raise exceptions.MQTTError

    def __exit__(self, *args):
        self._client.disconnect()
        self._client.loop_stop()
