from distutils.util import strtobool
import enum
import re

from tavern.util import exceptions


class _StrictSetting(enum.Enum):
    ON = 1
    OFF = 2
    UNSET = 3


valid_keys = ["json", "headers", "redirect_query_params"]


def _setting_factory(setting):
    """Converts from cmdlin/setting file to an enum"""
    if setting is None:
        return _StrictSetting.UNSET
    else:
        parsed = strtobool(setting)

        if parsed:
            return _StrictSetting.ON
        else:
            return _StrictSetting.OFF


class _StrictOption:
    def __init__(self, section, setting):
        self.section = section
        self.setting = _setting_factory(setting)

    def is_on(self):
        if self.section == "json":
            # Must be specifically disabled for response body
            return self.setting != _StrictSetting.OFF
        else:
            # Off by default for everything else
            return self.setting == _StrictSetting.ON


def validate_and_parse_option(key):
    regex = r"(?P<section>{})(:(?P<setting>on|off))?".format("|".join(valid_keys))

    match = re.fullmatch(regex, key)

    if not match:
        raise exceptions.InvalidConfigurationException(
            "Invalid value for 'strict' given - expected one of {}, got '{}'".format(
                valid_keys, key
            )
        )

    return _StrictOption(**match.groupdict())


class StrictLevel:
    def __init__(self, option):
        if isinstance(option, str):
            option = [option]

        self.matched = [validate_and_parse_option(key) for key in option]

    def setting_for(self, setting):
        return self.matched[setting]
