import attr
import copy

from tavern.util.strict_util import _StrictSetting


@attr.s(frozen=True)
class TavernInternalConfig:
    """Internal config that should be used only by tavern"""

    pytest_hook_caller = attr.ib()
    backends = attr.ib(type=dict)


@attr.s(frozen=True)
class TestConfig:
    """Tavern configuration - there is aglobal config, then test-specific config, and finally stage-specific config, but they all use this structure

    Attributes:
        follow_redirects (bool): whether the test should follow redirects
        variables (dict): variables available for use in the stage
        strict: Strictness for test/stage
        merge_ext_values (bool): Merge in values from 'ext' functions rather than replacing all existing data for the test
    """

    variables = attr.ib(type=dict)
    strict = attr.ib(type=_StrictSetting)
    follow_redirects = attr.ib(type=bool)
    merge_ext_values = attr.ib(type=bool)
    stages = attr.ib(type=list)

    tavern_internal = attr.ib(type=TavernInternalConfig)

    def copy(self):
        return copy.copy(self)
