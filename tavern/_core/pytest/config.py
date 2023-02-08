import copy
import dataclasses
import logging
from typing import Any

from tavern._core.strict_util import StrictSetting


@dataclasses.dataclass(frozen=True)
class TavernInternalConfig:
    """Internal config that should be used only by tavern"""

    pytest_hook_caller: Any
    backends: dict


@dataclasses.dataclass(frozen=True)
class TestConfig:
    """Tavern configuration - there is a global config, then test-specific config, and
    finally stage-specific config, but they all use this structure

    Attributes:
        follow_redirects: whether the test should follow redirects
        variables: variables available for use in the stage
        strict: Strictness for test/stage
    """

    variables: dict
    strict: StrictSetting
    follow_redirects: bool
    stages: list

    tavern_internal: TavernInternalConfig

    def copy(self) -> "TestConfig":
        # Use a deep copy, otherwise variables can leak into subsequent tests
        logger = logging.getLogger(__name__)
        logger.critical(self.variables)
        return dataclasses.replace(self, variables=copy.deepcopy(self.variables))

    def with_strictness(self, new_strict: StrictSetting) -> "TestConfig":
        """Create a copy of the config but with a new strictness setting"""
        return dataclasses.replace(self, strict=new_strict)
