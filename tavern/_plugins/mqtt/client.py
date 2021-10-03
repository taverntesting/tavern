import logging
from queue import Empty, Full, Queue
import ssl
import threading
import time

import paho.mqtt.client as paho

from tavern._core import exceptions
from tavern._core.dict_util import check_expected_keys

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


class _Subscription(object):
    def __init__(self, topic, subscribed=False):
        self.topic = topic
        self.subscribed = subscribed


def _handle_tls_args(tls_args):
    """Make sure TLS options are valid"""

    if not tls_args:
        return None

    if "enable" in tls_args:
        if not tls_args["enable"]:
            # if enable=false, return immediately
            return None

    if "keyfile" in tls_args and "certfile" not in tls_args:
        raise exceptions.MQTTTLSError(
            "If specifying a TLS keyfile, a certfile also needs to be specified"
        )

    def check_file_exists(key):
        try:
            with open(tls_args[key], "r", encoding="utf-8"):
                pass
        except IOError as e:
            raise exceptions.MQTTTLSError(
                "Couldn't load '{}' from '{}'".format(key, tls_args[key])
            ) from e
        except KeyError:
            pass

    # could be moved to schema validation stage
    check_file_exists("certfile")
    check_file_exists("keyfile")

    # This shouldn't raise an AttributeError because it's enumerated
    try:
        tls_args["cert_reqs"] = getattr(ssl, tls_args["cert_reqs"])
    except KeyError:
        pass

    try:
        tls_args["tls_version"] = getattr(ssl, tls_args["tls_version"])
    except AttributeError as e:
        raise exceptions.MQTTTLSError(
            "Error getting TLS version from "
            "ssl module - ssl module had no attribute '{}'. Check the "
            "documentation for the version of python you're using to see "
            "if this a valid option.".format(tls_args["tls_version"])
        ) from e
    except KeyError:
        pass

    return tls_args


class MQTTClient:
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
            "connect": {"host", "port", "keepalive", "timeout"},
            "tls": {
                "enable",
                "ca_certs",
                "cert_reqs",
                "certfile",
                "keyfile",
                "tls_version",
                "ciphers",
            },
            "auth": {"username", "password"},
        }

        logger.debug("Initialising MQTT client with %s", kwargs)

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
        file_tls_args = kwargs.pop("tls", {})
        check_expected_keys(expected_blocks["tls"], file_tls_args)
        self._tls_args = _handle_tls_args(file_tls_args)
        logger.debug("TLS is %s", "enabled" if self._tls_args else "disabled")

        logger.debug("Paho client args: %s", self._client_args)
        self._client = paho.Client(**self._client_args)
        self._client.enable_logger()

        if self._auth_args:
            self._client.username_pw_set(**self._auth_args)

        self._client.on_message = self._on_message

        if self._tls_args:
            try:
                self._client.tls_set(**self._tls_args)
            except ValueError as e:
                # tls_set only raises ValueErrors directly
                raise exceptions.MQTTTLSError("Unexpected error enabling TLS") from e
            except ssl.SSLError as e:
                # incorrect cipher, etc.
                raise exceptions.MQTTTLSError(
                    "Unexpected SSL error enabling TLS"
                ) from e

        # Arbitrary number, could just be 1 and only accept 1 message per stages
        # but we might want to raise an error if more than 1 message is received
        # during a test stage.
        self._message_queue = Queue(maxsize=10)
        self._userdata = {"queue": self._message_queue}
        self._client.user_data_set(self._userdata)

        # Topics to subscribe to - mapping of subscription message id to a tuple
        # of (topic, sub_status) where sub_status is true or false based on
        # whether it has finished subscribing or not
        self._subscribed = {}
        # Lock to ensure there is no race condition when subscribing
        self._subscribe_lock = threading.RLock()
        # callback
        self._client.on_subscribe = self._on_subscribe

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

    def publish(self, topic, payload=None, qos=None, retain=None):
        """publish message using paho library"""
        self._wait_for_subscriptions()

        logger.debug("Publishing on '%s'", topic)

        kwargs = {}
        if qos is not None:
            kwargs["qos"] = qos
        if retain is not None:
            kwargs["retain"] = retain
        msg = self._client.publish(topic, payload, **kwargs)

        if not msg.is_published:
            raise exceptions.MQTTError(
                "err {:s}: {:s}".format(
                    _err_vals.get(msg.rc, "unknown"), paho.error_string(msg.rc)
                )
            )

        return msg

    def _wait_for_subscriptions(self):
        """Wait for all pending subscriptions to finish"""
        logger.debug("Checking subscriptions")

        def not_finished_subscribing_to():
            """Get topic names for topics which have not finished subcribing to"""
            return [i.topic for i in self._subscribed.values() if not i.subscribed]

        to_wait_for = not_finished_subscribing_to()

        if to_wait_for:
            elapsed = 0.0
            while elapsed < self._connect_timeout:
                # TODO
                # configurable?
                time.sleep(0.25)
                elapsed += 0.25

                to_wait_for = not_finished_subscribing_to()

                if not to_wait_for:
                    break

                logger.debug(
                    "Not finished subscribing to '%s' after %.2f seconds",
                    to_wait_for,
                    elapsed,
                )

            if to_wait_for:
                logger.warning(
                    "Did not finish subscribing to '%s' before publishing - going ahead anyway",
                    to_wait_for,
                )

        if not to_wait_for:
            logger.debug("Finished subscribing to all topics")

    def subscribe(self, topic, *args, **kwargs):
        """Subscribe to topic

        should be called for every expected message in mqtt_response
        """
        logger.debug("Subscribing to topic '%s'", topic)

        with self._subscribe_lock:
            (status, mid) = self._client.subscribe(topic, *args, **kwargs)

            if status == 0:
                self._subscribed[mid] = _Subscription(topic, False)
            else:
                logger.error("Error subscribing to '%s'", topic)

    def unsubscribe_all(self):
        """Unsubscribe from all topics"""
        with self._subscribe_lock:
            for subscription in self._subscribed.values():
                self._client.unsubscribe(subscription.topic)

    def _on_subscribe(self, client, userdata, mid, granted_qos):
        # pylint: disable=unused-argument
        with self._subscribe_lock:
            if mid in self._subscribed:
                self._subscribed[mid].subscribed = True
                logger.debug(
                    "Successfully subscribed to '%s'", self._subscribed[mid].topic
                )
            else:
                logger.warning(
                    "Got SUBACK message with mid '%s', but did not recognise that mid - will try later",
                    mid,
                )

    def __enter__(self):
        logger.debug("Connecting to %s", self._connect_args)

        self._client.connect_async(**self._connect_args)
        self._client.loop_start()

        elapsed = 0

        while elapsed < self._connect_timeout:
            # pylint: disable=protected-access
            if self._client.is_connected():
                logger.debug("Connected to broker at %s", self._connect_args["host"])
                return self
            else:
                logger.debug("Not connected after %s seconds - waiting", elapsed)

            # TODO
            # configurable?
            time.sleep(0.25)
            elapsed += 0.25

        self._disconnect()
        logger.error(
            "Could not connect to broker after %s seconds", self._connect_timeout
        )
        raise exceptions.MQTTError

    def __exit__(self, *args):
        self._disconnect()

    def _disconnect(self):
        self._client.disconnect()
        self._client.loop_stop()
