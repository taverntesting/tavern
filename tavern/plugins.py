"""VERY simple skeleton for plugin stuff

This is here mainly to make MQTT easier, this will almost defintiely change
significantly if/when a proper plugin system is implemented!
"""
import logging

import stevedore
from future.utils import raise_from

from .util import exceptions

logger = logging.getLogger(__name__)


class PluginHelperBase(object):
    """Base for plugins"""


def plugin_load_error(mgr, entry_point, err):
    """ Handle import errors
    """
    # pylint: disable=unused-argument
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


class _PluginCache(object):
    # pylint: disable=inconsistent-return-statements

    def __init__(self):
        self.plugins = {}

    def __call__(self, config=None):
        if not config and not self.plugins:
            raise exceptions.PluginLoadError("No config to load plugins from")
        elif self.plugins:
            return self.plugins
        elif not self.plugins and config:
            # NOTE
            # This is reloaded every time
            self.plugins = self._load_plugins(config)
            return self.plugins

    def _load_plugins(self, test_block_config):
        """Load plugins from the 'tavern' entrypoint namespace

        This can be a module or a class as long as it defines the right things

        Todo:
            - Limit which plugins are loaded based on some config/command line
              option
            - Different plugin names
        """
        # pylint: disable=no-self-use

        plugins = []

        for backend in ["http", "mqtt"]:
            namespace = "tavern_{}".format(backend)

            def enabled(ext):
                # pylint: disable=cell-var-from-loop
                return ext.name == test_block_config["backends"][backend]

            manager = stevedore.EnabledExtensionManager(
                namespace=namespace,
                check_func=enabled,
                verify_requirements=True,
                on_load_failure_callback=plugin_load_error,
            )
            manager.propagate_map_exceptions = True

            manager.map(is_valid_reqresp_plugin)

            if len(manager.extensions) != 1:
                raise exceptions.MissingSettingsError("Expected exactly one entrypoint in 'tavern-{}' namespace but got {}".format(backend, len(manager.extensions)))

            plugins.extend(manager.extensions)

        return plugins


load_plugins = _PluginCache()


def get_extra_sessions(test_spec, test_block_config):
    """Get extra 'sessions' for any extra test types

    Args:
        test_spec (dict): Spec for the test block

    Returns:
        dict: mapping of name: session. Session should be a context manager.
    """

    sessions = {}

    plugins = load_plugins(test_block_config)

    for p in plugins:
        if any((p.plugin.request_block_name in i or p.plugin.response_block_name in i) for i in test_spec["stages"]):
            logger.debug("Initialising session for %s (%s)", p.name, p.plugin.session_type)
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

    plugins = load_plugins(test_block_config)

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
            logger.debug("Initialising request class for %s (%s)", p.name, request_class)
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

    plugins = load_plugins(test_block_config)

    expected = {}

    for p in plugins:
        if p.plugin.response_block_name in stage:
            logger.debug("Getting expected response for %s", p.name)
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

    plugins = load_plugins(test_block_config)

    verifiers = []

    for p in plugins:
        if p.plugin.response_block_name in stage:
            session = sessions[p.name]
            logger.debug("Initialising verifier for %s (%s)", p.name, p.plugin.verifier_type)
            verifier = p.plugin.verifier_type(session, stage["name"], expected[p.name], test_block_config)
            verifiers.append(verifier)

    return verifiers
