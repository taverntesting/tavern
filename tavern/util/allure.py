import logging
from textwrap import dedent

import allure

from tavern.util.formatted_str import FormattedString
from tavern.util.stage_lines import get_stage_lines, read_relevant_lines

logger = logging.getLogger(__name__)


def prepare_yaml(val):
    formatted = val

    if isinstance(val, dict):
        formatted = {}
        # formatted = {key: format_keys(val[key], box_vars) for key in val}
        for key in val:
            formatted[key] = prepare_yaml(val[key])
    elif isinstance(val, (list, tuple)):
        formatted = [prepare_yaml(item) for item in val]
    elif isinstance(formatted, FormattedString):
        return str(formatted)
    else:
        logger.debug("Not formatting something of type '%s'", type(formatted))

    return formatted


def allure_attach_stage_content(stage):
    first_line, last_line, _ = get_stage_lines(stage)

    code_lines = list(read_relevant_lines(stage, first_line, last_line))
    joined = dedent("\n".join(code_lines))
    allure_attach_yaml(joined, name="stage_yaml")


def allure_attach_yaml(payload, name):
    return allure_attach(payload, name, allure.attachment_type.YAML)


def allure_attach(payload, name, attachment_type=None):
    return allure.attach(payload, name=name, attachment_type=attachment_type)


def allure_wrap_step(allure_name, partial):
    return allure.step(allure_name)(partial)
