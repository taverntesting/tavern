from unittest.mock import patch

import pytest

from tavern._core import exceptions
from tavern.core import run


@pytest.fixture(autouse=True)
def patch_pytest():
    with patch("tavern.core.pytest.main") as fake_main:
        yield

    assert fake_main.called


class TestBasicRun:
    def test_run(self):
        run("")

    def test_run_with_empty_cfg(self):
        run("", {})

    def test_run_with_cfg(self):
        run("", {"a": 2})

    @pytest.mark.parametrize(
        "expected_kwarg",
        ("tavern_mqtt_backend", "tavern_http_backend", "tavern_strict"),
    )
    def test_doesnt_warn_about_expected_kwargs(self, expected_kwarg):
        kw = {expected_kwarg: 123}
        with pytest.warns(None) as warn_rec:
            run("", **kw)

        assert not len(warn_rec)


class TestParseGlobalCfg:
    def test_path_correct(self):
        run("", tavern_global_cfg=__file__)

    def test_pass_dict(self):
        run("", tavern_global_cfg={"variables": {"a": 1}})


class TestParseFailures:
    @pytest.fixture(autouse=True)
    def patch_pytest(self):
        with patch("tavern.core.pytest.main") as fake_main:
            yield

        assert not fake_main.called

    def test_path_nonexistent(self):
        with pytest.raises(exceptions.InvalidSettingsError):
            run("", tavern_global_cfg="sdfsdd")

    def test_bad_type(self):
        with pytest.raises(exceptions.InvalidSettingsError):
            run("", tavern_global_cfg=["a", "b", "c"])
