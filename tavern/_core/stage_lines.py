import logging
from typing import Optional, Protocol

logger: logging.Logger = logging.getLogger(__name__)


class EmptyBlock:
    line: int = 0
    name: Optional[str] = None


class _WithMarks(Protocol):
    start_mark: EmptyBlock
    end_mark: EmptyBlock


def get_stage_lines(stage: _WithMarks):
    first_line = start_mark(stage).line - 1
    last_line = end_mark(stage).line
    line_start = first_line + 1

    return first_line, last_line, line_start


def read_relevant_lines(yaml_block: _WithMarks, first_line: int, last_line: int):
    """Get lines between start and end mark"""

    filename = get_stage_filename(yaml_block)

    if filename is None:
        logger.warning("unable to read yaml block")
        return

    with open(filename, encoding="utf8") as testfile:
        for idx, line in enumerate(testfile.readlines()):
            if first_line < idx < last_line:
                yield line.split("#", 1)[0].rstrip()


def get_stage_filename(yaml_block: _WithMarks) -> str:
    return start_mark(yaml_block).name


def start_mark(yaml_block: _WithMarks):
    try:
        return yaml_block.start_mark
    except AttributeError:
        return EmptyBlock


def end_mark(yaml_block: _WithMarks):
    try:
        return yaml_block.end_mark
    except AttributeError:
        return EmptyBlock
