"""VERY simple skeleton for plugin stuff

This is here mainly to make MQTT easier, this will almost defintiely change
significantly if/when a proper plugin system is implemented!
"""

import dataclasses
import logging
from collections.abc import Callable, Mapping
from functools import partial
from typing import Any, Optional, Protocol

import stevedore

from tavern._core import exceptions
from tavern._core.dict_util import format_keys
from tavern._core.pytest.config import TestConfig
from tavern.request import BaseRequest
from tavern.response import BaseResponse

logger: logging.Logger = logging.getLogger(__name__)


class PluginHelperBase:
    """Base for plugins"""


def plugin_load_error(mgr, entry_point, err):
    """Handle import errors"""
    msg = f"Error loading plugin {entry_point} - {err}"
    raise exceptions.PluginLoadError(msg) from err


class _TavernPlugin(Protocol):
    """A tavern plugin"""

    session_type: type[Any]
    request_type: type[BaseRequest]
    verifier_type: type[BaseResponse]
    response_block_name: str
    request_block_name: str
    schema: Mapping

    def get_expected_from_request(
        self, response_block: BaseResponse, test_block_config: TestConfig, session: Any
    ) -> Any: ...


def is_valid_reqresp_plugin(ext: stevedore.extension.Extension) -> bool:
    """Whether this is a valid 'reqresp' plugin

    Requires certain functions/variables to be present

    Todo:
        Not all of these are required for all request/response types probably

    Args:
        ext: class or module plugin object

    Returns:
        Whether the plugin has everything we need to use it
    """
    required = [
        # MQTTClient, requests.Session
        "session_type",
        # RestRequest, MQTTRequest
        "request_type",
        # request, mqtt_publish, grpc_request
        "request_block_name",
        # Some function that returns a dict
        "get_expected_from_request",
        # MQTTResponse, RestResponse
        "verifier_type",
        # response, mqtt_response, grpc_request
        "response_block_name",
        # dictionary with pykwalify schema
        "schema",
    ]

    plugin: _TavernPlugin = ext.plugin

    return all(hasattr(plugin, i) for i in required)


class _Plugin:
    """Wrapped tavern plugin for convenience"""

    name: str
    plugin: _TavernPlugin


@dataclasses.dataclass
class _PluginCache:
    plugins: list[_Plugin] = dataclasses.field(default_factory=list)

    def __call__(self, config: Optional[TestConfig] = None) -> list[_Plugin]:
        if self.plugins:
            return self.plugins

        if config:
            # NOTE: This is reloaded every time
            self.plugins = self._load_plugins(config)
            return self.plugins

        raise exceptions.PluginLoadError("No config to load plugins from")

    def _load_plugins(self, test_block_config: TestConfig) -> list[_Plugin]:
        """Load plugins from the 'tavern' entrypoint namespace

        This can be a module or a class as long as it defines the right things

        Todo:
            - Limit which plugins are loaded based on some config/command line
              option
            - Different plugin names

        Args:
            test_block_config: available config for test

        Raises:
            exceptions.MissingSettingsError: invalid entry points set

        Returns:
            Loaded plugins, can be a class or a module
        """

        plugins = []

        def enabled(current_backend, ext):
            return (
                ext.name == test_block_config.tavern_internal.backends[current_backend]
            )

        for backend in test_block_config.backends():
            logger.debug("loading backend for %s", backend)

            namespace = f"tavern_{backend}"

            manager = stevedore.EnabledExtensionManager(
                namespace=namespace,
                check_func=partial(enabled, backend),
                verify_requirements=True,
                on_load_failure_callback=plugin_load_error,
            )
            manager.propagate_map_exceptions = True

            manager.map(is_valid_reqresp_plugin)

            if len(manager.extensions) != 1:
                raise exceptions.MissingSettingsError(
                    f"Expected exactly one entrypoint in 'tavern-{backend}' namespace but got {len(manager.extensions)}"
                )

            plugins.extend(manager.extensions)

        return plugins


load_plugins = _PluginCache()


def get_extra_sessions(test_spec: Mapping, test_block_config: TestConfig) -> dict:
    """Get extra 'sessions' for any extra test types

    Args:
        test_spec: Spec for the test block
        test_block_config: available config for test

    Returns:
        mapping of name to session. Session should be a context manager.
    """

    sessions = {}

    plugins = load_plugins(test_block_config)

    for p in plugins:
        if any(
            (p.plugin.request_block_name in i or p.plugin.response_block_name in i)
            for i in test_spec["stages"]
        ):
            logger.debug(
                "Initialising session for %s (%s)", p.name, p.plugin.session_type
            )
            session_spec = test_spec.get(p.name, {})
            formatted = format_keys(session_spec, test_block_config.variables)
            sessions[p.name] = p.plugin.session_type(**formatted)

    return sessions


def get_request_type(
    stage: Mapping,
    test_block_config: TestConfig,
    sessions: Mapping,
) -> BaseRequest:
    """Get the request object for this stage

    there can only be one

    Args:
        stage: spec for this stage
        test_block_config: variables for this test run
        sessions: all available sessions

    Returns:
        request object with a run() method

    Raises:
        exceptions.DuplicateKeysError: More than one kind of request specified
        exceptions.MissingKeysError: No request type specified
    """

    plugins = load_plugins(test_block_config)

    keys = {}

    for p in plugins:
        keys[p.plugin.request_block_name] = p.plugin.request_type

    if len(set(keys) & set(stage)) > 1:
        raise exceptions.DuplicateKeysError(
            f"Can only specify 1 request type but got {set(keys)}"
        )
    elif not list(set(keys) & set(stage)):
        raise exceptions.MissingKeysError(
            f"Need to specify one of valid request types: '{set(keys.keys())}'"
        )

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
            logger.debug(
                "Initialising request class for %s (%s)", p.name, request_class
            )
            break

    request_maker = request_class(session, request_args, test_block_config)

    return request_maker


class ResponseVerifier(dict):
    plugin_name: str


def _foreach_response(
    stage: Mapping,
    test_block_config: TestConfig,
    action: Callable[[_Plugin, str], dict],
) -> dict[str, dict]:
    """Do something for each response

    Args:
        stage: Stage of test
        test_block_config: Config for test
        action: function that takes (plugin, response block)

    Returns:
        mapping of plugin name to list of expected (normally length 1)
    """

    plugins = load_plugins(test_block_config)

    retvals = {}

    for p in plugins:
        response_block = stage.get(p.plugin.response_block_name)
        if response_block is not None:
            retvals[p.name] = action(p, response_block)

    return retvals


def get_expected(
    stage: Mapping,
    test_block_config: TestConfig,
    sessions: Mapping,
):
    """Get expected responses for each type of request

    Though only 1 request can be made, it can cause multiple responses.

    Because we need to subcribe to MQTT topics, which might be formatted from
    keys from included files, the 'expected'/'response' needs to be formatted
    BEFORE running the request.

    Args:
        stage: test stage
        test_block_config: available configuration for this test
        sessions: all available sessions

    Returns:
        mapping of request type to expected response dict
    """

    def action(p, response_block):
        plugin_expected = p.plugin.get_expected_from_request(
            response_block, test_block_config, sessions[p.name]
        )
        if plugin_expected:
            plugin_expected = ResponseVerifier(**plugin_expected)
            plugin_expected.plugin_name = p.name
            return plugin_expected
        else:
            return None

    return _foreach_response(stage, test_block_config, action)


def get_verifiers(
    stage: Mapping,
    test_block_config: TestConfig,
    sessions: Mapping,
    expected: Mapping,
):
    """Get one or more response validators for this stage

    Args:
        stage: spec for this stage
        test_block_config: variables for this test run
        sessions: all available sessions
        expected: expected responses for this stage

    Returns:
        response validator object with a verify(response) method
    """

    def action(p, _):
        session = sessions[p.name]
        logger.debug(
            "Initialising verifier for %s (%s)", p.name, p.plugin.verifier_type
        )
        verifiers = []

        plugin_expected = expected[p.name]

        verifier = p.plugin.verifier_type(
            session, stage["name"], plugin_expected, test_block_config
        )
        verifiers.append(verifier)

        return verifiers

    return _foreach_response(stage, test_block_config, action)
