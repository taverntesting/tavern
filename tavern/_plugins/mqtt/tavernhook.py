import logging

from tavern.util.dict_util import format_keys

from .request import MQTTRequest
from .response import MQTTResponse
from .client import MQTTClient


logger = logging.getLogger(__name__)


session_type = MQTTClient

request_type = MQTTRequest
request_block_name = "mqtt_publish"

def get_expected_from_request(stage, test_block_config, session):
    # mqtt response is not required
    m_expected = stage.get("mqtt_response")
    if m_expected:
        # format so we can subscribe to the right topic
        f_expected = format_keys(m_expected, test_block_config["variables"])
        mqtt_client = session
        mqtt_client.subscribe(f_expected["topic"])
        expected = f_expected
    else:
        expected = {}

    return expected

verifier_type = MQTTResponse
response_block_name = "mqtt_response"
