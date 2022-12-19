import pytest

from tavern._core.strict_util import StrictOption, StrictSetting, extract_strict_setting


@pytest.mark.parametrize(
    "strict", [True, StrictSetting.ON, StrictOption("json", StrictSetting.ON)]
)
def test_extract_strict_setting_true(strict):
    as_bool, as_setting = extract_strict_setting(strict)
    assert as_bool is True
    if isinstance(strict, StrictSetting):
        assert as_setting == strict
    if isinstance(strict, StrictOption):
        assert as_setting == strict.setting


@pytest.mark.parametrize(
    "strict",
    [
        False,
        StrictSetting.OFF,
        StrictSetting.LIST_ANY_ORDER,
        StrictSetting.UNSET,
        StrictOption("json", StrictSetting.OFF),
        None,
    ],
)
def test_extract_strict_setting_false(strict):
    as_bool, as_setting = extract_strict_setting(strict)
    assert as_bool is False
    if isinstance(strict, StrictSetting):
        assert as_setting == strict
    if isinstance(strict, StrictOption):
        assert as_setting == strict.setting
