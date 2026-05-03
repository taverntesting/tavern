"""Tests for global tinctures support via tavern-global-cfg (issue #969)."""
from unittest.mock import MagicMock, patch

import pytest

from tavern._core import exceptions
from tavern._core.pytest.config import TavernInternalConfig, TestConfig
from tavern._core.strict_util import StrictLevel


def _make_test_config(tinctures=None):
    """Helper to create a minimal TestConfig with optional global tinctures."""
    return TestConfig(
        variables={},
        strict=StrictLevel.none,
        follow_redirects=True,
        stages=[],
        tavern_internal=TavernInternalConfig(
            pytest_hook_caller=MagicMock(),
            backends={},
        ),
        tinctures=tinctures or [],
    )


class TestNormalizeTinctures:
    """Tests for tinctures normalization in _load_global_cfg."""

    def test_none_becomes_empty_list(self):
        from tavern._core.pytest.util import _load_global_cfg
        mock_config = MagicMock()
        with patch("tavern._core.pytest.util.load_global_config", return_value={"tinctures": None}), \
             patch("tavern._core.pytest.util._load_global_strictness", return_value=StrictLevel.none), \
             patch("tavern._core.pytest.util._load_global_follow_redirects", return_value=True), \
             patch("tavern._core.pytest.util._load_global_backends", return_value={}):
            cfg = _load_global_cfg(mock_config)
        assert cfg.tinctures == []

    def test_dict_wrapped_in_list(self):
        from tavern._core.pytest.util import _load_global_cfg
        tincture = {"function": "mymodule:my_func"}
        mock_config = MagicMock()
        with patch("tavern._core.pytest.util.load_global_config", return_value={"tinctures": tincture}), \
             patch("tavern._core.pytest.util._load_global_strictness", return_value=StrictLevel.none), \
             patch("tavern._core.pytest.util._load_global_follow_redirects", return_value=True), \
             patch("tavern._core.pytest.util._load_global_backends", return_value={}):
            cfg = _load_global_cfg(mock_config)
        assert cfg.tinctures == [tincture]

    def test_list_passed_through(self):
        from tavern._core.pytest.util import _load_global_cfg
        tinctures = [{"function": "mymodule:func1"}, {"function": "mymodule:func2"}]
        mock_config = MagicMock()
        with patch("tavern._core.pytest.util.load_global_config", return_value={"tinctures": tinctures}), \
             patch("tavern._core.pytest.util._load_global_strictness", return_value=StrictLevel.none), \
             patch("tavern._core.pytest.util._load_global_follow_redirects", return_value=True), \
             patch("tavern._core.pytest.util._load_global_backends", return_value={}):
            cfg = _load_global_cfg(mock_config)
        assert cfg.tinctures == tinctures

    def test_invalid_type_raises_bad_schema_error(self):
        from tavern._core.pytest.util import _load_global_cfg
        mock_config = MagicMock()
        with patch("tavern._core.pytest.util.load_global_config", return_value={"tinctures": "invalid"}), \
             patch("tavern._core.pytest.util._load_global_strictness", return_value=StrictLevel.none), \
             patch("tavern._core.pytest.util._load_global_follow_redirects", return_value=True), \
             patch("tavern._core.pytest.util._load_global_backends", return_value={}):
            with pytest.raises(exceptions.BadSchemaError):
                _load_global_cfg(mock_config)

    def test_no_tinctures_key_defaults_to_empty_list(self):
        from tavern._core.pytest.util import _load_global_cfg
        mock_config = MagicMock()
        with patch("tavern._core.pytest.util.load_global_config", return_value={}), \
             patch("tavern._core.pytest.util._load_global_strictness", return_value=StrictLevel.none), \
             patch("tavern._core.pytest.util._load_global_follow_redirects", return_value=True), \
             patch("tavern._core.pytest.util._load_global_backends", return_value={}):
            cfg = _load_global_cfg(mock_config)
        assert cfg.tinctures == []


class TestGlobalTincturesMergedInRunStage:
    """Tests that global tinctures from TestConfig are merged with stage tinctures."""

    def test_global_tinctures_appended_to_stage_tinctures(self):
        """Global tinctures should be appended to stage-level tinctures in run_stage."""
        from tavern._core.run import _TestRunner

        global_tincture_fn = {"function": "mymodule:global_func"}
        test_config = _make_test_config(tinctures=[global_tincture_fn])
        stage = {"name": "step 1", "request": {"url": "http://example.com", "method": "GET"}}
        test_spec = {"test_name": "test", "stages": [stage]}

        mock_wrapped = MagicMock()
        with patch("tavern._core.run.get_stage_tinctures") as mock_get_stage, \
             patch("tavern._core.run.get_wrapped_response_function", return_value=mock_wrapped), \
             patch("tavern._core.run.retry", return_value=lambda fn: fn), \
             patch.object(_TestRunner, "wrapped_run_stage"):
            mock_tinctures = MagicMock()
            mock_get_stage.return_value = mock_tinctures

            runner = _TestRunner.__new__(_TestRunner)
            runner.default_global_strictness = StrictLevel.none
            runner.sessions = {}
            runner.test_block_config = test_config
            runner.test_spec = test_spec
            runner.run_stage(0, stage)

        mock_tinctures.tinctures.append.assert_called_once_with(mock_wrapped)

    def test_no_global_tinctures_no_append(self):
        """When no global tinctures, append is never called."""
        from tavern._core.run import _TestRunner

        test_config = _make_test_config(tinctures=[])
        stage = {"name": "step 1", "request": {"url": "http://example.com", "method": "GET"}}
        test_spec = {"test_name": "test", "stages": [stage]}

        with patch("tavern._core.run.get_stage_tinctures") as mock_get_stage, \
             patch("tavern._core.run.get_wrapped_response_function") as mock_wrap, \
             patch("tavern._core.run.retry", return_value=lambda fn: fn), \
             patch.object(_TestRunner, "wrapped_run_stage"):
            mock_tinctures = MagicMock()
            mock_get_stage.return_value = mock_tinctures

            runner = _TestRunner.__new__(_TestRunner)
            runner.default_global_strictness = StrictLevel.none
            runner.sessions = {}
            runner.test_block_config = test_config
            runner.test_spec = test_spec
            runner.run_stage(0, stage)

        mock_wrap.assert_not_called()
        mock_tinctures.tinctures.append.assert_not_called()
