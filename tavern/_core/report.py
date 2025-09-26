import logging
from textwrap import dedent
from typing import Union

import yaml

try:
    from allure import attach, step
    from allure import attachment_type as at

    yaml_type = at.YAML
except ImportError:
    yaml_type = None

    def attach(*args, **kwargs) -> None:
        logger.debug("Not attaching anything as allure is not installed")

    def step(name):
        def call(step_func):
            return step_func

        return call


from tavern._core.formatted_str import FormattedString
from tavern._core.stage_lines import get_stage_lines, read_relevant_lines

logger: logging.Logger = logging.getLogger(__name__)


def prepare_yaml(val: Union[dict, set, list, tuple, str]) -> Union[dict, list, str]:
    """Sanitises the formatted string into a format safe for dumping"""
    if isinstance(val, dict):
        prepared = {}
        # formatted = {key: format_keys(val[key], box_vars) for key in val}
        for key in val:
            if isinstance(key, FormattedString):
                key = str(key)
            prepared[key] = prepare_yaml(val[key])

        return prepared
    elif isinstance(val, list | tuple | set):
        return [prepare_yaml(item) for item in val]
    elif isinstance(val, FormattedString):
        return str(val)

    return val


def attach_stage_content(stage: dict) -> None:
    first_line, last_line, _ = get_stage_lines(stage)

    code_lines = list(read_relevant_lines(stage, first_line, last_line))
    joined = dedent("\n".join(code_lines))
    attach_text(joined, "stage_yaml", yaml_type)


def attach_yaml(payload, name: str) -> None:
    prepared = prepare_yaml(payload)
    dumped = yaml.safe_dump(prepared)
    return attach_text(dumped, name, yaml_type)


def attach_text(payload, name: str, attachment_type=None) -> None:
    return attach(payload, name=name, attachment_type=attachment_type)


def wrap_step(allure_name: str, partial):
    return step(allure_name)(partial)
