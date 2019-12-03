from distutils.util import strtobool
import enum
import re

import attr

from tavern.util import exceptions


class _StrictSetting(enum.Enum):
    ON = 1
    OFF = 2
    UNSET = 3


valid_keys = ["json", "headers", "redirect_query_params"]


def setting_factory(str_setting):
    """Converts from cmdline/setting file to an enum"""
    if str_setting is None:
        return _StrictSetting.UNSET
    else:
        parsed = strtobool(str_setting)

        if parsed:
            return _StrictSetting.ON
        else:
            return _StrictSetting.OFF


@attr.s(frozen=True)
class _StrictOption:
    section = attr.ib(type=str)
    setting = attr.ib(type=_StrictSetting)

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
                ["{}[:on/off]".format(key) for key in valid_keys], key
            )
        )

    as_dict = match.groupdict()
    return _StrictOption(as_dict["section"], setting_factory(as_dict["setting"]))


@attr.s(frozen=True)
class StrictLevel:
    json = attr.ib(default=_StrictOption("json", setting_factory(None)))
    headers = attr.ib(default=_StrictOption("headers", setting_factory(None)))
    redirect_query_params = attr.ib(
        default=_StrictOption("redirect_query_params", setting_factory(None))
    )

    @classmethod
    def from_options(cls, options):
        if isinstance(options, str):
            options = [options]
        elif not isinstance(options, list):
            raise exceptions.InvalidConfigurationException(
                "'strict' setting should be a list of strings"
            )

        parsed = [validate_and_parse_option(key) for key in options]

        return cls(**{i.section: i for i in parsed})

    def setting_for(self, section):
        """Provides a string-based way of getting strict settings for a section"""
        try:
            return getattr(self, section)
        except AttributeError as e:
            raise exceptions.InvalidConfigurationException(
                "No setting for '{}'".format(section)
            ) from e

    @classmethod
    def all_on(cls):
        return cls.from_options([i + ":on" for i in valid_keys])

    @classmethod
    def all_off(cls):
        return cls.from_options([i + ":off" for i in valid_keys])
