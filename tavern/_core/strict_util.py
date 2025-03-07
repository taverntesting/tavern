import dataclasses
import enum
import logging
import re
from typing import Optional, Union

from tavern._core import exceptions
from tavern._core.strtobool import strtobool

logger: logging.Logger = logging.getLogger(__name__)


class StrictSetting(enum.Enum):
    """The actual setting for a particular block"""

    ON = 1
    OFF = 2
    UNSET = 3
    LIST_ANY_ORDER = 4


valid_keys = ["json", "headers", "redirect_query_params"]

valid_switches = ["on", "off", "list_any_order"]


def strict_setting_factory(str_setting: Optional[str]) -> StrictSetting:
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


@dataclasses.dataclass(frozen=True)
class StrictOption:
    """The section and the setting. The setting is only stored here because json works slightly
    differently, otherwise it's redundant"""

    section: str
    setting: StrictSetting

    def is_on(self) -> bool:
        if self.section == "json":
            # Must be specifically disabled for response body
            return self.setting not in [StrictSetting.OFF, StrictSetting.LIST_ANY_ORDER]
        else:
            # Off by default for everything else
            return self.setting in [StrictSetting.ON]


def validate_and_parse_option(key: str) -> StrictOption:
    regex = re.compile(
        "(?P<section>{sections})(:(?P<setting>{switches}))?".format(
            sections="|".join(valid_keys), switches="|".join(valid_switches)
        )
    )

    match = regex.fullmatch(key)

    if not match:
        raise exceptions.InvalidConfigurationException(
            "Invalid value for 'strict' given - expected one of {}, got '{}'".format(
                [f"{key}[:on/off]" for key in valid_keys], key
            )
        )

    as_dict = match.groupdict()

    if as_dict["section"] != "json" and as_dict["setting"] == "list_any_order":
        logger.warning(
            "Using 'list_any_order' key outside of 'json' section has no meaning"
        )

    return StrictOption(as_dict["section"], strict_setting_factory(as_dict["setting"]))


@dataclasses.dataclass(frozen=True)
class StrictLevel:
    """Strictness settings for every block in a response

    TODO: change the name of this class, it's awful"""

    json: StrictOption = dataclasses.field(
        default=StrictOption("json", strict_setting_factory(None))
    )
    headers: StrictOption = dataclasses.field(
        default=StrictOption("headers", strict_setting_factory(None))
    )
    redirect_query_params: StrictOption = dataclasses.field(
        default=StrictOption("redirect_query_params", strict_setting_factory(None))
    )

    @classmethod
    def from_options(cls, options: Union[list[str], str]) -> "StrictLevel":
        if isinstance(options, str):
            options = [options]
        elif not isinstance(options, list):
            raise exceptions.InvalidConfigurationException(
                "'strict' setting should be a list of strings"
            )

        logger.debug("Parsing options to strict level: %s", options)

        parsed = [validate_and_parse_option(key) for key in options]

        return cls(**{i.section: i for i in parsed})

    def option_for(self, section: str) -> StrictOption:
        """Provides a string-based way of getting strict settings for a section"""
        try:
            return getattr(self, section)
        except AttributeError as e:
            raise exceptions.InvalidConfigurationException(
                f"No setting for '{section}'"
            ) from e

    @classmethod
    def all_on(cls) -> "StrictLevel":
        return cls.from_options([i + ":on" for i in valid_keys])

    @classmethod
    def all_off(cls) -> "StrictLevel":
        return cls.from_options([i + ":off" for i in valid_keys])


StrictSettingKinds = Union[None, bool, StrictSetting, StrictOption]


def extract_strict_setting(strict: StrictSettingKinds) -> tuple[bool, StrictSetting]:
    """Takes either a bool, StrictOption, or a StrictSetting and return the bool representation
    and StrictSetting representation"""

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
            f"Unable to parse strict setting '{strict}' of type '{type(strict)}'"
        )

    logger.debug("Got strict as '%s', setting as '%s'", strict, strict_setting)

    return strict, strict_setting
