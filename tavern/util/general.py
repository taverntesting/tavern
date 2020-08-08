import io
import logging

from tavern.util.loader import load_single_document_yaml
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
            contents = load_single_document_yaml(filename)
            global_cfg = deep_dict_merge(global_cfg, contents)

    return global_cfg


def read_relevant_lines(filename, first_line, last_line):
    """Get lines between start and end mark

    Args:
        filename (str): name of file to read
        first_line (int): beginning line
        last_line (int): last line

    Yields:
        str: subsequent lines from the input file
    """
    # Uses io.open for utf8
    with io.open(filename, "r", encoding="utf8") as testfile:
        for idx, line in enumerate(testfile.readlines()):
            if first_line < idx < last_line:
                yield line.split("#", 1)[0].rstrip()
