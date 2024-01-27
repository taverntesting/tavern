import logging
from collections.abc import MutableMapping
from typing import Any

from tavern._core.pytest.config import TestConfig

logger: logging.Logger = logging.getLogger(__name__)


def pytest_tavern_beta_before_every_test_run(test_dict: dict, variables: dict) -> None:
    """Called:

    - directly after fixtures are loaded for a test
    - directly before verifying the schema of the file
    - Before formatting is done on values
    - After global configuration has been loaded
    - After plugins have been loaded

    Modify the test in-place if you want to do something to it.

    Args:
        test_dict: Test to run
        variables: Available variables
    """


def pytest_tavern_beta_after_every_test_run(test_dict: dict, variables: dict) -> None:
    """Called:

    - After test run

    Args:
        test_dict: Test to run
        variables: Available variables
    """


def pytest_tavern_beta_after_every_response(expected: Any, response: Any) -> None:
    """Called after every _response_ - including MQTT/HTTP/etc

    Note:
        - The response object type and the expected dict depends on what plugin you're using, and which kind of response it is!
        - MQTT responses will call this hook multiple times if multiple messages are received

    Args:
        expected: Response block in stage
        response: Response object.
    """


def pytest_tavern_beta_before_every_request(request_args: MutableMapping) -> None:
    """Called just before every request - including MQTT/HTTP/etc

    Note:
        - The request object type depends on what plugin you're using, and which kind of request it is!

    Args:
        request_args: Arguments passed to the request function. By default, this is Session.request for
            HTTP and Client.publish for MQTT
    """


def call_hook(test_block_config: TestConfig, hookname: str, **kwargs) -> None:
    """Utility to call the hooks"""
    try:
        hook = getattr(test_block_config.tavern_internal.pytest_hook_caller, hookname)
    except AttributeError:
        logger.critical("Error getting tavern hook!")
        raise

    try:
        hook(**kwargs)
    except AttributeError:
        logger.error("Unexpected error calling tavern hook")
        raise
