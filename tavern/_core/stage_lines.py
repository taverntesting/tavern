import dataclasses
import logging
from collections.abc import Iterable, Mapping
from typing import (
    Optional,
    Protocol,
    Union,
)

logger: logging.Logger = logging.getLogger(__name__)


@dataclasses.dataclass
class YamlMark:
    """A pyyaml mark"""

    line: int = 0
    name: Optional[str] = None


class _WithMarks(Protocol):
    """Things loaded by pyyaml have these"""

    start_mark: YamlMark
    end_mark: YamlMark


PyYamlDict = Union[_WithMarks, Mapping]


def get_stage_lines(stage: PyYamlDict) -> tuple[int, int, int]:
    first_line = start_mark(stage).line - 1
    last_line = end_mark(stage).line
    line_start = first_line + 1

    return first_line, last_line, line_start


def read_relevant_lines(
    yaml_block: PyYamlDict, first_line: int, last_line: int
) -> Iterable[str]:
    """Get lines between start and end mark"""

    filename = get_stage_filename(yaml_block)

    if filename is None:
        logger.warning("unable to read yaml block")
        return

    with open(filename, encoding="utf8") as testfile:
        for idx, line in enumerate(testfile.readlines()):
            if first_line < idx < last_line:
                yield line.split("#", 1)[0].rstrip()


def get_stage_filename(yaml_block: PyYamlDict) -> Optional[str]:
    return start_mark(yaml_block).name


def start_mark(yaml_block: PyYamlDict) -> Union[type[YamlMark], YamlMark]:
    try:
        return yaml_block.start_mark  # type:ignore
    except AttributeError:
        return YamlMark()


def end_mark(yaml_block: PyYamlDict) -> Union[type[YamlMark], YamlMark]:
    try:
        return yaml_block.end_mark  # type:ignore
    except AttributeError:
        return YamlMark()
