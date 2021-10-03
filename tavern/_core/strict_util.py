from distutils.util import strtobool
import enum
import logging
import re

import attr

from tavern._core import exceptions

logger = logging.getLogger(__name__)


class StrictSetting(enum.Enum):
    ON = 1
    OFF = 2
    UNSET = 3
    LIST_ANY_ORDER = 4


valid_keys = ["json", "headers", "redirect_query_params"]

valid_switches = ["on", "off", "list_any_order"]


def strict_setting_factory(str_setting):
    """Converts from cmdline/setting file to an enum"""
    if str_setting is None:
        return StrictSetting.UNSET
    else:
        if str_setting == "list_any_order":
            return StrictSetting.LIST_ANY_ORDER

        parsed = strtobool(str_setting)

        if parsed:
            return StrictSetting.ON
        else:
            return StrictSetting.OFF


@attr.s(frozen=True)
class StrictOption:
    section = attr.ib(type=str)
    setting = attr.ib(type=StrictSetting)

    def is_on(self):
        if self.section == "json":
            # Must be specifically disabled for response body
            return self.setting not in [StrictSetting.OFF, StrictSetting.LIST_ANY_ORDER]
        else:
            # Off by default for everything else
            return self.setting in [StrictSetting.ON]


def validate_and_parse_option(key):
    regex = re.compile(
        "(?P<section>{sections})(:(?P<setting>{switches}))?".format(
            sections="|".join(valid_keys), switches="|".join(valid_switches)
        )
    )

    match = regex.fullmatch(key)

    if not match:
        raise exceptions.InvalidConfigurationException(
            "Invalid value for 'strict' given - expected one of {}, got '{}'".format(
                ["{}[:on/off]".format(key) for key in valid_keys], key
            )
        )

    as_dict = match.groupdict()

    if as_dict["section"] != "json" and as_dict["setting"] == "list_any_order":
        logger.warning(
            "Using 'list_any_order' key outside of 'json' section has no meaning"
        )

    return StrictOption(as_dict["section"], strict_setting_factory(as_dict["setting"]))


@attr.s(frozen=True)
class StrictLevel:
    json = attr.ib(default=StrictOption("json", strict_setting_factory(None)))
    headers = attr.ib(default=StrictOption("headers", strict_setting_factory(None)))
    redirect_query_params = attr.ib(
        default=StrictOption("redirect_query_params", strict_setting_factory(None))
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


def extract_strict_setting(strict):
    """Takes either a bool, StrictOption, or a StrictSetting and return the bool representation and StrictSetting representation"""

    logger.debug("Parsing a '%s': %s", type(strict), strict)

    if isinstance(strict, StrictSetting):
        strict_setting = strict
        strict = strict == StrictSetting.ON
    elif isinstance(strict, StrictOption):
        strict_setting = strict.setting
        strict = strict.is_on()
    elif isinstance(strict, bool):
        strict_setting = strict_setting_factory(str(strict))
    elif strict is None:
        strict = False
        strict_setting = strict_setting_factory("false")
    else:
        raise exceptions.InvalidConfigurationException(
            "Unable to parse strict setting '{}' of type '{}'".format(
                strict, type(strict)
            )
        )

    return strict, strict_setting
