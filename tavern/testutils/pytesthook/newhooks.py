# pylint: disable=unused-argument
import logging

logger = logging.getLogger(__name__)


def pytest_tavern_beta_before_every_test_run(test_dict, variables, test_block_config):
    """Called:

    - directly after fixtures are loaded for a test
    - directly before verifying the schema of the file
    - Before formatting is done on values
    - After global configuration has been loaded
    - After plugins have been loaded

    Modify the test in-place if you want to do something to it.

    Args:
        test_dict (dict): Test to run.
        variables (dict): Available variables.
        test_block_config (dict): Test block config object.
    """


def pytest_tavern_beta_before_every_block_run(test_spec, test_block_config):
    """Called before every test_spec run.

    Note:
        -

    Args:
        test_spec (object): Test spec object.
        test_block_config (dict): Test block config object.
    """


def pytest_tavern_beta_before_every_request(request_args, test_block_config):
    """Called before every _request_ - including HTTP

    Note:
        - The request arguments object type depends on what plugin you're using.

    Args:
         request_args (object): Request arguments object.
        test_block_config (dict): Test block config object.
    """


def pytest_tavern_beta_after_every_response(expected, response, test_block_config):
    """Called after every _response_ - including MQTT/HTTP/etc

    Note:
        - The response object type and the expected dict depends on what plugin you're using, and which kind of response it is!
        - MQTT responses will call this hook multiple times if multiple messages are received

    Args:
        response (object): Response object.
        expected (dict): Response block in stage.
        test_block_config (dict): Test block config object.
    """


def call_hook(test_block_config, hookname, **kwargs):
    """Utility to call the hooks"""
    try:
        hook = getattr(
            test_block_config["tavern_internal"]["pytest_hook_caller"], hookname
        )
    except AttributeError:
        logger.critical("Error getting tavern hook!")
        raise

    try:
        hook(**kwargs)
    except AttributeError:
        logger.error("Unexpected error calling tavern hook")
        raise
