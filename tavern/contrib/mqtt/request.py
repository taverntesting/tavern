import logging
import json
import functools

from future.utils import raise_from
from box import Box

from tavern.util import exceptions
from tavern.util.dict_util import format_keys, check_expected_keys

from .base import BaseRequest


logger = logging.getLogger(__name__)


def get_publish_args(rspec, test_block_config):
    """Format mqtt request args

    Todo:
        Anything else to do here?
    """

    fspec = format_keys(rspec, test_block_config["variables"])

    if "json" in rspec:
        if "payload" in rspec:
            raise exceptions.BadSchemaError("Can only specify one of 'payload' or 'json' in MQTT request")

        fspec["payload"] = json.dumps(fspec.pop("json"))

    return fspec


class MQTTRequest(BaseRequest):
    """Wrapper for a single mqtt request on a client

    Similar to RestRequest, publishes a single message.
    """

    def __init__(self, client, rspec, test_block_config):
        expected = {
            "topic",
            "payload",
            "json",
            "qos",
            # TODO retain?
        }

        check_expected_keys(expected, rspec)

        publish_args = get_publish_args(rspec, test_block_config)

        self._prepared = functools.partial(client.publish, **publish_args)

        # Need to do this here because get_publish_args will modify the original
        # input, which we might want to use to format. No error handling because
        # all the error handling is done in the previous call
        self._original_publish_args = format_keys(rspec, test_block_config)

        # TODO
        # From paho:
        # > raise TypeError('payload must be a string, bytearray, int, float or None.')
        # Need to be able to take all of these somehow, and also match these
        # against any payload received on the topic

    def run(self):
        try:
            return self._prepared()
        except ValueError as e:
            logger.exception("Error publishing")
            raise_from(exceptions.MQTTRequestException, e)

    @property
    def request_vars(self):
        return Box(self._original_publish_args)
