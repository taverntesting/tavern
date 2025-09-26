import copy
import dataclasses
import logging
import ssl
import threading
import time
from collections.abc import Mapping, MutableMapping
from queue import Empty, Full, Queue
from typing import Any, Optional, Union

import paho.mqtt.client as paho
from paho.mqtt.client import MQTTMessageInfo

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

logger: logging.Logger = logging.getLogger(__name__)


@dataclasses.dataclass
class _Subscription:
    topic: str
    subscribed: bool = False

    # Arbitrary number, could just be 1 and only accept 1 message per stages
    # but we might want to raise an error if more than 1 message is received
    # during a test stage.
    queue: Queue = dataclasses.field(default_factory=lambda: Queue(maxsize=30))


def check_file_exists(key, filename) -> None:
    try:
        with open(filename, encoding="utf-8"):
            pass
    except OSError as e:
        raise exceptions.MQTTTLSError(f"Couldn't load '{key}' from '{filename}'") from e


def _handle_tls_args(
    tls_args: MutableMapping,
) -> Optional[Mapping]:
    """Make sure TLS options are valid"""

    if not tls_args:
        return None

    if "enable" in tls_args and not tls_args["enable"]:
        # if enable=false, return immediately
        return None

    _check_and_update_common_tls_args(tls_args, ["certfile", "keyfile"])

    return tls_args


def _handle_ssl_context_args(
    ssl_context_args: MutableMapping,
) -> Optional[Mapping]:
    """Make sure SSL Context options are valid"""
    if not ssl_context_args:
        return None

    _check_and_update_common_tls_args(
        ssl_context_args, ["certfile", "keyfile", "cafile"]
    )

    return ssl_context_args


def _check_and_update_common_tls_args(
    tls_args: MutableMapping, check_file_keys: list[str]
) -> None:
    """Checks common args between ssl/tls args"""

    # could be moved to schema validation stage
    for key in check_file_keys:
        if key in tls_args:
            check_file_exists(key, tls_args[key])

    if "keyfile" in tls_args and "certfile" not in tls_args:
        raise exceptions.MQTTTLSError(
            "If specifying a TLS keyfile, a certfile also needs to be specified"
        )

    if "cert_reqs" in tls_args:
        tls_args["cert_reqs"] = getattr(ssl, tls_args["cert_reqs"])

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


class MQTTClient:
    def __init__(self, **kwargs) -> None:
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
            "ssl_context": {
                "ca_certs",
                "certfile",
                "keyfile",
                "password",
                "tls_version",
                "ciphers",
                "alpn_protocols",
            },
        }

        sanitised_kwargs = copy.deepcopy(kwargs)
        if auth := kwargs.get("auth"):
            if "password" in auth:
                sanitised_kwargs["auth"]["password"] = "******"  # noqa

        logger.debug("Initialising MQTT client with %s", sanitised_kwargs)

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
            raise exceptions.MissingKeysError(msg)

        self._connect_timeout = self._connect_args.pop("timeout", 3)

        # If there is any tls or ssl_context kwarg, configure tls encryption
        file_tls_args = kwargs.pop("tls", {})
        file_ssl_context_args = kwargs.pop("ssl_context", {})

        if file_tls_args and file_ssl_context_args:
            msg = (
                "'tls' and 'ssl_context' are both specified but are mutually exclusive"
            )
            raise exceptions.MQTTTLSError(msg)

        check_expected_keys(expected_blocks["tls"], file_tls_args)
        self._tls_args = _handle_tls_args(file_tls_args)
        logger.debug("TLS is %s", "enabled" if self._tls_args else "disabled")

        # If there is any SSL kwarg, enable tls through the SSL context
        check_expected_keys(expected_blocks["ssl_context"], file_ssl_context_args)
        self._ssl_context_args = _handle_ssl_context_args(file_ssl_context_args)

        logger.debug("Paho client args: %s", self._client_args)
        self._client = paho.Client(**self._client_args)
        self._client.enable_logger()

        if self._auth_args:
            logger.debug("authenticating as '%s'", self._auth_args.get("username"))
            self._client.username_pw_set(**self._auth_args)

        self._client.on_message = self._on_message
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_connect_fail = self._on_connect_fail
        self._client.on_socket_open = self._on_socket_open
        self._client.on_socket_close = self._on_socket_close

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

        if self._ssl_context_args:
            # Create SSLContext object
            tls_version = self._ssl_context_args.get("tls_version")
            if tls_version is None:
                # If the python version supports it, use highest TLS version automatically
                if hasattr(ssl, "PROTOCOL_TLS_CLIENT"):
                    tls_version = ssl.PROTOCOL_TLS_CLIENT
                elif hasattr(ssl, "PROTOCOL_TLS"):
                    tls_version = ssl.PROTOCOL_TLS
                else:
                    tls_version = ssl.PROTOCOL_TLSv1_2
            ca_certs = self._ssl_context_args.get("cert_reqs")
            context = ssl.create_default_context(cafile=ca_certs)

            certfile = self._ssl_context_args.get("certfile")
            keyfile = self._ssl_context_args.get("keyfile")
            password = self._ssl_context_args.get("password")

            # Configure context
            if certfile is not None:
                context.load_cert_chain(certfile, keyfile, password)

            cert_reqs = self._ssl_context_args.get("cert_reqs")
            if cert_reqs == ssl.CERT_NONE and hasattr(context, "check_hostname"):
                context.check_hostname = False

            context.verify_mode = ssl.CERT_REQUIRED if cert_reqs is None else cert_reqs

            if ca_certs is not None:
                context.load_verify_locations(ca_certs)
            else:
                context.load_default_certs()

            ciphers = self._ssl_context_args.get("ciphers")
            if ciphers is not None:
                context.set_ciphers(ciphers)

            alpn_protocols = self._ssl_context_args.get("alpn_protocols")
            if alpn_protocols is not None:
                context.set_alpn_protocols(alpn_protocols)

            self._client.tls_set_context(context)

            if cert_reqs != ssl.CERT_NONE:
                # Default to secure, sets context.check_hostname attribute
                # if available
                self._client.tls_insecure_set(False)
            else:
                # But with ssl.CERT_NONE, we can not check_hostname
                self._client.tls_insecure_set(True)

        # Topics to subscribe to - mapping of subscription message id to subscription object
        self._subscribed: dict[int, _Subscription] = {}
        # Lock to ensure there is no race condition when subscribing
        self._subscribe_lock = threading.RLock()
        # callback
        self._client.on_subscribe = self._on_subscribe

        # Mapping of topic -> subscription id, for indexing into self._subscribed
        self._subscription_mappings: dict[str, int] = {}
        self._userdata = {
            "_subscription_mappings": self._subscription_mappings,
            "_subscribed": self._subscribed,
        }
        self._client.user_data_set(self._userdata)

    @staticmethod
    def _on_message(
        client, userdata: Mapping[str, Any], message: paho.MQTTMessage
    ) -> None:
        """Add any messages received to the queue

        Todo:
            If the queue is faull trigger an error in main thread somehow
        """

        logger.info("Received mqtt message on %s", message.topic)

        try:
            for sub_topic, sub_id in userdata["_subscription_mappings"].items():
                if paho.topic_matches_sub(sub_topic, message.topic):
                    userdata["_subscribed"][sub_id].queue.put(message)
                    break
            else:
                raise exceptions.MQTTTopicException(
                    f"Message received on unregistered topic: {message.topic}"
                )
        except Full:
            logger.exception("message queue full")

    @staticmethod
    def _on_connect(client, userdata, flags, rc: int) -> None:
        logger.debug(
            "Client '%s' connected to the broker with result code '%s'",
            client._client_id.decode(),
            paho.connack_string(rc),
        )

    @staticmethod
    def _on_disconnect(client, userdata, rc: int) -> None:
        if rc == paho.CONNACK_ACCEPTED:
            logger.debug(
                "Client '%s' successfully disconnected from the broker with result code '%s'",
                client._client_id.decode(),
                paho.connack_string(rc),
            )
        else:
            logger.warning(
                "Client %s failed to disconnect cleanly due to %s, possibly from a network error",
                client._client_id.decode(),
                paho.connack_string(rc),
            )

    @staticmethod
    def _on_connect_fail(client, userdata) -> None:
        logger.error(
            "Failed to connect client '%s' to the broker", client._client_id.decode()
        )

    @staticmethod
    def _on_socket_open(client, userdata, socket) -> None:
        logger.debug("MQTT socket opened")

    @staticmethod
    def _on_socket_close(client, userdata, socket) -> None:
        logger.debug("MQTT socket closed")

    def message_received(
        self, topic: str, timeout: Union[float, int] = 1
    ) -> Optional[paho.MQTTMessage]:
        """Check that a message is in the message queue

        Args:
            topic: topic to fetch message for
            timeout: How long to wait before signalling that the message
                was not received.

        Returns:
            the message, if one was received, otherwise None

        Todo:
            Allow regexes for topic names? Better validation for mqtt payloads
        """

        try:
            with self._subscribe_lock:
                queue = self._subscribed[self._subscription_mappings[topic]].queue
        except KeyError as e:
            raise exceptions.MQTTTopicException(f"Unregistered topic: {topic}") from e

        try:
            msg = queue.get(block=True, timeout=timeout)
        except Empty:
            logger.error("Message not received after %d seconds", timeout)
            return None

        return msg

    def publish(
        self,
        topic: str,
        payload: Optional[Any] = None,
        qos: Optional[int] = None,
        retain: Optional[bool] = False,
    ) -> MQTTMessageInfo:
        """publish message using paho library"""
        self._wait_for_subscriptions()

        logger.debug("Publishing on '%s'", topic)

        kwargs = {}
        if qos is not None:
            kwargs["qos"] = qos
        if retain is not None:
            kwargs["retain"] = retain
        msg = self._client.publish(topic, payload, **kwargs)

        # Wait for 2*connect timeout which should be plenty to publish the message even with qos 2
        # TODO: configurable
        try:
            msg.wait_for_publish(self._connect_timeout * 2)
        except (RuntimeError, ValueError) as e:
            raise exceptions.MQTTError("could not publish message") from e

        if not msg.is_published():
            raise exceptions.MQTTError(
                "err {:s}: {:s}".format(
                    _err_vals.get(msg.rc, "unknown"), paho.error_string(msg.rc)
                )
            )

        return msg

    def _wait_for_subscriptions(self) -> None:
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

    def subscribe(self, topic: str, *args, **kwargs) -> None:
        """Subscribe to topic

        should be called for every expected message in mqtt_response
        """
        logger.debug("Subscribing to topic '%s'", topic)

        (status, mid) = self._client.subscribe(topic, *args, **kwargs)

        if status == 0:
            with self._subscribe_lock:
                self._subscription_mappings[topic] = mid
                self._subscribed[mid] = _Subscription(topic)
        else:
            raise exceptions.MQTTError(
                f"Error subscribing to '{topic}' (err code {status})"
            )

    def unsubscribe_all(self) -> None:
        """Unsubscribe from all topics"""
        with self._subscribe_lock:
            for subscription in self._subscribed.values():
                self._client.unsubscribe(subscription.topic)

    def _on_subscribe(self, client, userdata, mid: int, granted_qos) -> None:
        with self._subscribe_lock:
            if mid in self._subscribed:
                self._subscribed[mid].subscribed = True
                logger.debug(
                    "Successfully subscribed to '%s'", self._subscribed[mid].topic
                )
            else:
                logger.debug("Only tracking: %s", self._subscribed.keys())
                logger.warning(
                    "Got SUBACK message with mid '%s', but did not recognise that mid - will try later",
                    mid,
                )

    def __enter__(self) -> "MQTTClient":
        logger.debug("Connecting to %s", self._connect_args)

        self._client.connect_async(**self._connect_args)
        self._client.loop_start()

        elapsed = 0.0

        while elapsed < self._connect_timeout:
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

    def __exit__(self, *args) -> None:
        self._disconnect()

    def _disconnect(self) -> None:
        self._client.disconnect()
        self._client.loop_stop()
