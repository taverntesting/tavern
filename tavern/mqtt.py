import logging
import time

try:
    from queue import Queue, Full, Empty
except ImportError:
    from Queue import Queue, Full, Empty

import paho.mqtt.client as paho

from .util.keys import check_expected_keys
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

    def __init__(self, **kwargs):
        expected_main = {
            "client",
            "tls",
            "connect",
        }

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
            }
        }

        # check main block first
        check_expected_keys(expected_main, kwargs)

        # then check constructor/connect/tls_set args
        self._client_args = kwargs.pop("client", {})
        check_expected_keys(expected_blocks["client"], self._client_args)

        self._connect_args = kwargs.pop("connect", {})
        check_expected_keys(expected_blocks["connect"], self._connect_args)

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

        self._client = paho.Client(**self._client_args)

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
        try:
            userdata["queue"].put(message)
        except Full:
            logger.exception("message queue full")

    def message_received(self, topic, payload, timeout=1):
        """Check that a message is in the message queue

        Args:
            topic (str): topic message should have been on
            payload (str, dict): expected payload - can be a str or a dict...?
            timeout (int): How long to wait before signalling that the message
                was not received.

        Returns:
            bool: whether the message was received within the timeout

        Todo:
            Allow regexes for topic names? Better validation for mqtt payloads
        """

        time_spent = 0

        while time_spent < timeout:
            t1 = time.time()
            try:
                msg = self._message_queue.get(block=True, timeout=timeout)
            except Empty:
                time_spent += timeout
            else:
                time_spent += time.time() - t1
                if msg.payload != payload and msg.topic != topic:
                    # TODO
                    # Error?
                    logger.warning("Got unexpected message in '%s' with payload '%s'",
                        msg.topic, msg.payload)
                else:
                    logger.warning("Got expected message in '%s' with payload '%s'",
                        msg.topic, msg.payload)

                    return True

        logger.error("Message not received in time")
        return False

    def publish(self, topic, *args, **kwargs):
        """publish message using paho library
        """
        logger.debug("Publishing on %s", topic)
        msg = self._client.publish(topic, *args, **kwargs)

        if not msg.is_published:
            raise exceptions.MQTTError("err {:s}: {:s}".format(_err_vals[msg.rc], paho.error_string(msg.rc)))

    def __enter__(self):
        self._client.connect_async(**self._connect_args)
        self._client.loop_start()

        elapsed = 0

        while elapsed < self._connect_timeout:
            # TODO
            # configurable?
            time.sleep(0.25)
            elapsed += 0.25

            if self._client._state == paho.mqtt_cs_connected:
                logger.debug("Connected to broker at %s", self._connect_args["host"])
                return self
            else:
                logger.debug("Not connected after %s seconds - waiting", elapsed)

        logger.error("Could not connect to broker after %s seconds", self._connect_timeout)
        raise exceptions.MQTTError

    def __exit__(self, *args):
        self._client.loop_stop()

    # TODO
    # collect message received - have a queue that collects messages with
    # on_message callback and then have a expected_message method which checks
    # that a certain message was received. Also need a clear_queue or something
    # to run at the beginning of each stage to clear this queue.
