import logging

logger = logging.getLogger(__name__)


def hook_emmit(test_block_config, hookname, **kwargs):
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
