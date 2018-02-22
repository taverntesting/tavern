"""VERY simple skeleton for plugin stuff

This is here mainly to make MQTT easier, this will almost defintiely change
significantly if/when a proper plugin system is implemented!
"""
import logging
import requests

from future.utils import raise_from

from .util.dict_util import format_keys
from .util import exceptions
from .request import RestRequest, MQTTRequest
from .response import RestResponse, MQTTResponse

logger = logging.getLogger(__name__)


def get_extra_sessions(test_spec):
    """Get extra 'sessions' for any extra test types

    Args:
        test_spec (dict): Spec for the test block

    Returns:
        dict: mapping of name: session. Session should be a context manager.
    """

    sessions = {}

    # always used at the moment
    requests_session = requests.Session()
    sessions["requests"] = requests_session

    if "mqtt" in test_spec:
        # FIXME
        # this makes it hard to patch out, will need fixing when prooper plugin
        # system is put in
        from .mqtt import MQTTClient
        try:
            mqtt_client = MQTTClient(**test_spec["mqtt"])
        except exceptions.MQTTError:
            logger.exception("Error initializing mqtt connection")
            raise

        sessions["mqtt"] = mqtt_client

    return sessions


def get_request_type(stage, test_block_config, sessions):
    """Get the request object for this stage

    there can only be one

    Args:
        stage (dict): spec for this stage
        test_block_config (dict): variables for this test run
        sessions (dict): all available sessions

    Returns:
        BaseRequest: request object with a run() method
    """

    keys = {
        "request": RestRequest,
        "mqtt_publish": MQTTRequest,
    }

    if len(set(keys) & set(stage)) > 1:
        logger.error("Can only specify 1 request type")
        raise exceptions.DuplicateKeysError
    elif not list(set(keys) & set(stage)):
        logger.error("Need to specify one of '%s'", keys.keys())
        raise exceptions.MissingKeysError

    if "request" in stage:
        rspec = stage["request"]

        session = sessions["requests"]

        r = RestRequest(session, rspec, test_block_config)
    elif "mqtt_publish" in stage:
        session = sessions["mqtt"]

        try:
            mqtt_client = sessions["mqtt"]
        except KeyError as e:
            logger.error("No mqtt settings but stage wanted to send an mqtt message")
            raise_from(exceptions.MissingSettingsError, e)

        rspec = stage["mqtt_publish"]

        r = MQTTRequest(mqtt_client, rspec, test_block_config)

    return r


def get_expected(stage, test_block_config, sessions):
    """Get expected responses for each type of request

    Though only 1 request can be made, it can cause multiple responses.

    Because we need to subcribe to MQTT topics, which might be formatted from
    keys from included files, the 'expected'/'response' needs to be formatted
    BEFORE running the request.

    Args:
        stage (dict): test stage
        sessions (dict): all available sessions

    Returns:
        dict: mapping of request type: expected response dict
    """

    expected = {}

    if "request" in stage:
        try:
            r_expected = stage["response"]
        except KeyError as e:
            logger.error("Need a 'response' block if a 'request' is being sent")
            raise_from(exceptions.MissingSettingsError, e)

        f_expected = format_keys(r_expected, test_block_config["variables"])
        expected["requests"] = f_expected

    if "mqtt_response" in stage:
        # mqtt response is not required
        m_expected = stage.get("mqtt_response")
        if m_expected:
            # format so we can subscribe to the right topic
            f_expected = format_keys(m_expected, test_block_config["variables"])
            mqtt_client = sessions["mqtt"]
            mqtt_client.subscribe(f_expected["topic"])
            expected["mqtt"] = f_expected
        else:
            expected["mqtt"] = m_expected

    return expected


def get_verifiers(stage, test_block_config, sessions, expected):
    """Get one or more response validators for this stage

    Args:
        stage (dict): spec for this stage
        test_block_config (dict): variables for this test run
        sessions (dict): all available sessions
        expected (dict): expected responses for this stage

    Returns:
        BaseResponse: response validator object with a verify(response) method
    """

    # keys = {
    #     "request": RestResponse,
    #     "mqtt_publish": MQTTResponse,
    # }

    verifiers = []

    if "response" in stage:
        session = sessions["requests"]
        verifiers.append(RestResponse(session, stage["name"], expected["requests"], test_block_config))

    if "mqtt_response" in stage:
        mqtt_client = sessions["mqtt"]
        verifiers.append(MQTTResponse(mqtt_client, stage["name"], expected["mqtt"], test_block_config))

    return verifiers
