import copy
import dataclasses
from typing import Any

from tavern._core.strict_util import StrictSetting


@dataclasses.dataclass(frozen=True)
class TavernInternalConfig:
    """Internal config that should be used only by tavern"""

    pytest_hook_caller: Any
    backends: dict


@dataclasses.dataclass(frozen=True)
class TestConfig:
    """Tavern configuration - there is aglobal config, then test-specific config, and finally stage-specific config, but they all use this structure

    Attributes:
        follow_redirects (bool): whether the test should follow redirects
        variables (dict): variables available for use in the stage
        strict: Strictness for test/stage
    """

    variables: dict
    strict: StrictSetting
    follow_redirects: bool
    stages: list

    tavern_internal: TavernInternalConfig

    def copy(self):
        return copy.copy(self)

    def with_strictness(self, new_strict):
        return dataclasses.replace(self, strict=new_strict)
