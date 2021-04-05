import logging
from os.path import abspath, dirname, join

import yaml

from tavern.util.dict_util import format_keys

from .client import MQTTClient
from .request import MQTTRequest
from .response import MQTTResponse

logger = logging.getLogger(__name__)

session_type = MQTTClient

request_type = MQTTRequest
request_block_name = "mqtt_publish"


def _get_subscriptions(expected):
    def get(i):
        return i["topic"], i["qos"]

    if isinstance(expected, dict):
        return [get(expected)]
    elif isinstance(expected, list):
        return [get(i) for i in expected]


def get_expected_from_request(response_block, test_block_config, session):
    expected = None
    # mqtt response is not required
    if response_block:
        # format so we can subscribe to the right topic
        f_expected = format_keys(response_block, test_block_config.variables)
        mqtt_client = session
        mqtt_client.subscribe(response_block["topic"], response_block.get("qos", 1))
        expected = f_expected

    return expected


verifier_type = MQTTResponse
response_block_name = "mqtt_response"

schema_path = join(abspath(dirname(__file__)), "jsonschema.yaml")
with open(schema_path, "r", encoding="utf-8") as schema_file:
    schema = yaml.load(schema_file, Loader=yaml.SafeLoader)
