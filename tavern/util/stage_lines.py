import io
import logging

logger = logging.getLogger(__name__)


def get_stage_lines(stage):
    first_line = start_mark(stage).line - 1
    last_line = end_mark(stage).line
    line_start = first_line + 1

    return first_line, last_line, line_start


def read_relevant_lines(yaml_block, first_line, last_line):
    """Get lines between start and end mark"""

    filename = start_mark(yaml_block).name

    if filename is None:
        logger.warning("unable to read yaml block")
        return

    with io.open(filename, "r", encoding="utf8") as testfile:
        for idx, line in enumerate(testfile.readlines()):
            if first_line < idx < last_line:
                yield line.split("#", 1)[0].rstrip()


class EmptyBlock:
    line = 0
    name = None


def start_mark(yaml_block):
    try:
        return yaml_block.start_mark
    except AttributeError:
        return EmptyBlock


def end_mark(yaml_block):
    try:
        return yaml_block.end_mark
    except AttributeError:
        return EmptyBlock
