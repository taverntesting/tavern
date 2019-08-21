# pylint: disable=unused-argument
import logging

logger = logging.getLogger(__name__)


def pytest_tavern_before_every_test_run(test_dict, variables):
    """Called:

    - directly after fixtures are loaded for a test
    - directly before verifying the schema of the file
    - Before formatting is done on values
    - After fixtures have been resolved
    - After global configuration has been loaded
    - After plugins have been loaded

    Modify the test in-place if you want to do something to it.

    Args:
        test_dict (dict): Test to run
        variables (dict): Available variables
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
        logger.error("Error calling tavern hook!")
        raise
