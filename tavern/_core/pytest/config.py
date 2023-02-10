import copy
import dataclasses
from typing import Any

from tavern._core.strict_util import StrictLevel


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
        stages: Any extra stages imported from other config files
    """

    variables: dict
    strict: StrictLevel
    follow_redirects: bool
    stages: list

    tavern_internal: TavernInternalConfig

    def copy(self) -> "TestConfig":
        """Returns a shallow copy of self"""
        return copy.copy(self)

    def with_new_variables(self) -> "TestConfig":
        """Returns a shallow copy of self but with the variables copied. This stops things being
        copied between tests. Can't use deepcopy because the variables might contain things that
        can't be pickled and hence can't be deep copied."""
        copied = self.copy()
        return dataclasses.replace(copied, variables=copy.copy(self.variables))

    def with_strictness(self, new_strict: StrictLevel) -> "TestConfig":
        """Create a copy of the config but with a new strictness setting"""
        return dataclasses.replace(self, strict=new_strict)
