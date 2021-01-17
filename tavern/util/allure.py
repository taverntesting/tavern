import logging

import allure

from tavern.util.formatted_str import FormattedString

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


def allure_attach_yaml(payload, name):
    return allure_attach(payload, name, allure.attachment_type.YAML)


def allure_attach(payload, name, attachment_type=None):
    return allure.attach(payload=payload, name=name, attachment_type=attachment_type)


def allure_wrap_step(allure_name, partial):
    return allure.step(allure_name)(partial)
