import logging
import functools

from future.utils import raise_from

from tavern.util import exceptions
from tavern.util.dict_util import format_keys
from tavern.util.keys import check_expected_keys

from .base import BaseRequest


logger = logging.getLogger(__name__)


def get_publish_args(rspec, test_block_config):
    """Format mqtt request args

    Todo:
        Anything else to do here?
    """

    try:
        fspec = format_keys(rspec, test_block_config["variables"])
    except exceptions.MissingFormatError as e:
        logger.error("Key(s) not found in format: %s", e.args)
        raise

    return fspec


class MQTTRequest(BaseRequest):
    """Wrapper for a single mqtt request on a client

    Similar to RestRequest, publishes a single message.
    """

    def __init__(self, client, rspec, test_block_config):
        expected = {
            "topic",
            "payload",
            "qos",
            # TODO retain?
        }

        check_expected_keys(expected, rspec)

        publish_args = get_publish_args(rspec, test_block_config)

        self._prepared = functools.partial(client.publish, **publish_args)

    def run(self):
        try:
            return self._prepared()
        except ValueError as e:
            logger.exception("Error publishing")
            raise_from(exceptions.MQTTRequestException, e)
