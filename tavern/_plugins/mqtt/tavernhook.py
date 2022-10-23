import logging
from os.path import abspath, dirname, join

import yaml

from tavern._core.dict_util import format_keys

from .client import MQTTClient
from .request import MQTTRequest
from .response import MQTTResponse

logger = logging.getLogger(__name__)

session_type = MQTTClient

request_type = MQTTRequest
request_block_name = "mqtt_publish"


def get_expected_from_request(response_block, test_block_config, session):
    expected = None

    # mqtt response is not required
    if response_block:
        expected = {"mqtt_responses": []}
        if isinstance(response_block, dict):
            response_block = [response_block]

        for response in response_block:
            # format so we can subscribe to the right topic
            f_expected = format_keys(response, test_block_config.variables)
            mqtt_client = session
            mqtt_client.subscribe(f_expected["topic"], f_expected.get("qos", 1))
            expected["mqtt_responses"].append(f_expected)

    return expected


verifier_type = MQTTResponse
response_block_name = "mqtt_response"

schema_path = join(abspath(dirname(__file__)), "jsonschema.yaml")
with open(schema_path, "r", encoding="utf-8") as schema_file:
    schema = yaml.load(schema_file, Loader=yaml.SafeLoader)
