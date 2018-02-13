import logging
import functools

from tavern.util.keys import check_expected_keys


logger = logging.getLogger(__name__)


class MQTTRequest(object):
    """Wrapper for a single mqtt request on a client

    Similar to TRequest, publishes a single message.
    """

    def __init__(self, client, mqtt_block_config):
        expected = {
            "topic",
            "payload",
            "qos",
            # TODO retain?
        }

        check_expected_keys(expected, mqtt_block_config)

        self._prepared = functools.partial(client.publish, **mqtt_block_config)

    def run(self):
        return self._prepared()
