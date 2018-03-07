import logging
import yaml
from .dict_util import deep_dict_merge


logger = logging.getLogger(__name__)


def load_global_config(global_cfg_paths):
    """Given a list of file paths to global config files, load each of them and
    return the joined dictionary.

    This does a deep dict merge.

    Args:
        global_cfg_paths (list(str)): List of filenames to load from

    Returns:
        dict: joined global configs
    """
    global_cfg = {}

    if global_cfg_paths:
        logger.debug("Loading global config from %s", global_cfg_paths)
        for filename in global_cfg_paths:
            with open(filename, "r") as gfileobj:
                contents = yaml.load(gfileobj)

            global_cfg = deep_dict_merge(global_cfg, contents)

    return global_cfg
