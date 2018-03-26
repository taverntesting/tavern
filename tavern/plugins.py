"""VERY simple skeleton for plugin stuff

This is here mainly to make MQTT easier, this will almost defintiely change
significantly if/when a proper plugin system is implemented!
"""
import logging
import requests

import yaml
import stevedore
from future.utils import raise_from

from .util.dict_util import format_keys
from .util import exceptions
# from .request import RestRequest, MQTTRequest
# from .response import RestResponse, MQTTResponse

logger = logging.getLogger(__name__)


class PluginHelperBase(object):
    def __init__(self):
        try:
            with open(self.schema_path, "r") as schema_file:
                self.schema = yaml.load(schema_file)
        except AttributeError as e:
            raise_from(exceptions.PluginLoadError("No file '{}' to load schema from".format(self.schema_path)))


def plugin_load_error(mgr, entry_point, err):
    """ Handle import errors
    """
    msg = "Error loading plugin {} - {}".format(entry_point, err)
    raise_from(exceptions.PluginLoadError(msg), err)


def is_valid_reqresp_plugin(ext):
    """Whether this is a valid 'reqresp' plugin

    Requires certain functions/variables to be present

    Todo:
        Not all of these are required for all request/response types probably
    """
    required = [
        # MQTTClient, requests.Session
        "session_type",
        # RestRequest, MQTTRequest
        "request_type",
        # request, mqtt_publish
        "request_block_name",
        # Some function that returns a dict
        "get_expected_from_request",
        # MQTTResponse, RestResponse
        "verifier_type",
        # response, mqtt_response
        "response_block_name",
        # dictionary with pykwalify schema
        "schema",
    ]

    return all(hasattr(ext.plugin, i) for i in required)


def load_plugins():
    """Load plugins from the 'tavern' entrypoint namespace

    This can be a module or a class as long as it defines the right things

    Todo:
        - Limit which plugins are loaded based on some config/command line
          option
        - Different plugin names
    """
    def enabled(ext):
        return True
        # Is this at all useful for testing...?
        if ext.name not in ["http", "mqtt"]:
            raise NotImplementedError("Currently only supports 'http' and 'mqtt' blocks")

    manager = stevedore.EnabledExtensionManager(
        namespace="tavern",
        check_func=enabled,
        verify_requirements=True,
        on_load_failure_callback=plugin_load_error,
    )
    manager.propagate_map_exceptions = True

    manager.map(is_valid_reqresp_plugin)

    return manager


def get_extra_sessions(test_spec):
    """Get extra 'sessions' for any extra test types

    Args:
        test_spec (dict): Spec for the test block

    Returns:
        dict: mapping of name: session. Session should be a context manager.
    """

    sessions = {}

    plugins = load_plugins()

    for p in plugins:
        # TODO
        # change to test_spec["plugins"].get(....)
        sessions[p.name] = p.plugin.session_type(**test_spec.get(p.name, {}))

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

    plugins = load_plugins()

    keys = {}

    for p in plugins:
        keys[p.plugin.request_block_name] = p.plugin.request_type

    if len(set(keys) & set(stage)) > 1:
        logger.error("Can only specify 1 request type")
        raise exceptions.DuplicateKeysError
    elif not list(set(keys) & set(stage)):
        logger.error("Need to specify one of '%s'", keys.keys())
        raise exceptions.MissingKeysError

    # We've validated that 1 and only 1 is there, so just loop until the first
    # one is found
    for p in plugins:
        try:
            request_args = stage[p.plugin.request_block_name]
        except KeyError:
            pass
        else:
            session = sessions[p.name]
            request_class = p.plugin.request_type
            break

    request_maker = request_class(session, request_args, test_block_config)

    return request_maker


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

    plugins = load_plugins()

    expected = {}

    for p in plugins:
        plugin_expected = p.plugin.get_expected_from_request(stage, test_block_config, sessions[p.name])
        expected[p.name] = plugin_expected

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
