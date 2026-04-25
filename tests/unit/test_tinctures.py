from unittest.mock import patch

import pytest

from tavern._core.pytest.config import TavernInternalConfig, TestConfig
from tavern._core.strict_util import StrictLevel
from tavern._core.tincture import Tinctures, get_stage_tinctures


@pytest.fixture(name="example")
def example():
    spec = {
        "test_name": "A test with a single stage",
        "stages": [
            {
                "name": "step 1",
                "request": {"url": "http://www.google.com", "method": "GET"},
                "response": {
                    "status_code": 200,
                    "json": {"key": "value"},
                    "headers": {"content-type": "application/json"},
                },
            }
        ],
    }

    return spec


@pytest.fixture(name="mock_internal_config")
def mock_internal_config():
    """Create a mock TavernInternalConfig for testing"""
    from unittest.mock import Mock

    return TavernInternalConfig(pytest_hook_caller=Mock(), backends={})


def make_test_config(tinctures=None, mock_internal_config=None):
    """Helper to create TestConfig objects for testing"""
    if mock_internal_config is None:
        from unittest.mock import Mock

        mock_internal_config = TavernInternalConfig(
            pytest_hook_caller=Mock(), backends={}
        )
    return TestConfig(
        variables={},
        strict=StrictLevel.all_off(),
        follow_redirects=False,
        stages=[],
        tavern_internal=mock_internal_config,
        tinctures=tinctures,
    )


def test_empty():
    t = Tinctures([])

    t.start_tinctures({})
    t.end_tinctures({}, None)


@pytest.mark.parametrize(
    "tinctures",
    (
        {"function": "abc"},
        [{"function": "abc"}],
        [{"function": "abc"}, {"function": "def"}],
    ),
)
class TestTinctures:
    class TestTinctureBasic:
        def test_stage_tinctures_normal(self, example, tinctures):
            stage = example["stages"][0]
            stage["tinctures"] = tinctures

            with patch(
                "tavern._core.tincture.get_wrapped_response_function",
                return_value=lambda _: None,
            ) as call_mock:
                t = get_stage_tinctures(stage, example)

            t.start_tinctures(stage)
            t.end_tinctures(stage, None)

            assert call_mock.call_count == len(tinctures)

        def test_test_tinctures_normal(self, example, tinctures):
            stage = example["stages"][0]
            example["tinctures"] = tinctures

            with patch(
                "tavern._core.tincture.get_wrapped_response_function",
                return_value=lambda _: None,
            ) as call_mock:
                t = get_stage_tinctures(stage, example)

            t.start_tinctures(stage)
            t.end_tinctures(stage, None)

            assert call_mock.call_count == len(tinctures)

    class TestTinctureYields:
        @staticmethod
        def does_yield(stage):
            assert stage["name"] == "step 1"

            (expected, response) = yield

            assert expected == stage["response"]
            assert response is None

        def test_stage_tinctures_normal(self, example, tinctures):
            stage = example["stages"][0]
            stage["tinctures"] = tinctures

            with patch(
                "tavern._core.tincture.get_wrapped_response_function",
                return_value=self.does_yield,
            ) as call_mock:
                t = get_stage_tinctures(stage, example)

            t.start_tinctures(stage)
            t.end_tinctures(stage["response"], None)

            assert call_mock.call_count == len(tinctures)

        def test_test_tinctures_normal(self, example, tinctures):
            stage = example["stages"][0]
            example["tinctures"] = tinctures

            with patch(
                "tavern._core.tincture.get_wrapped_response_function",
                return_value=self.does_yield,
            ) as call_mock:
                t = get_stage_tinctures(stage, example)

            t.start_tinctures(stage)
            t.end_tinctures(stage["response"], None)

            assert call_mock.call_count == len(tinctures)


class TestGlobalTinctures:
    """Tests for global tinctures feature (issue #969)"""

    @pytest.mark.parametrize(
        "global_tinctures",
        (
            {"function": "global_func"},
            [{"function": "global_func"}],
            [{"function": "global_func1"}, {"function": "global_func2"}],
        ),
    )
    def test_global_tinctures_only(
        self, example, mock_internal_config, global_tinctures
    ):
        """Test that global tinctures are applied when no test/stage tinctures exist"""
        stage = example["stages"][0]
        global_cfg = make_test_config(
            tinctures=global_tinctures, mock_internal_config=mock_internal_config
        )

        with patch(
            "tavern._core.tincture.get_wrapped_response_function",
            return_value=lambda _: None,
        ) as call_mock:
            t = get_stage_tinctures(stage, example, global_cfg)

        t.start_tinctures(stage)
        t.end_tinctures(stage, None)

        expected_count = (
            1 if isinstance(global_tinctures, dict) else len(global_tinctures)
        )
        assert call_mock.call_count == expected_count

    def test_global_tinctures_combined_with_test_tinctures(
        self, example, mock_internal_config
    ):
        """Test that global tinctures are combined with test-level tinctures"""
        stage = example["stages"][0]
        example["tinctures"] = [{"function": "test_func"}]
        global_cfg = make_test_config(
            tinctures=[{"function": "global_func"}],
            mock_internal_config=mock_internal_config,
        )

        with patch(
            "tavern._core.tincture.get_wrapped_response_function",
            return_value=lambda _: None,
        ) as call_mock:
            t = get_stage_tinctures(stage, example, global_cfg)

        t.start_tinctures(stage)
        t.end_tinctures(stage, None)

        # 1 test tincture + 1 global tincture = 2 total
        assert call_mock.call_count == 2

    def test_global_tinctures_combined_with_stage_tinctures(
        self, example, mock_internal_config
    ):
        """Test that global tinctures are combined with stage-level tinctures"""
        stage = example["stages"][0]
        stage["tinctures"] = [{"function": "stage_func"}]
        global_cfg = make_test_config(
            tinctures=[{"function": "global_func"}],
            mock_internal_config=mock_internal_config,
        )

        with patch(
            "tavern._core.tincture.get_wrapped_response_function",
            return_value=lambda _: None,
        ) as call_mock:
            t = get_stage_tinctures(stage, example, global_cfg)

        t.start_tinctures(stage)
        t.end_tinctures(stage, None)

        # 1 stage tincture + 1 global tincture = 2 total
        assert call_mock.call_count == 2

    def test_global_tinctures_combined_with_all_levels(
        self, example, mock_internal_config
    ):
        """Test that global tinctures are combined with both test and stage tinctures"""
        stage = example["stages"][0]
        example["tinctures"] = [{"function": "test_func"}]
        stage["tinctures"] = [{"function": "stage_func"}]
        global_cfg = make_test_config(
            tinctures=[{"function": "global_func"}],
            mock_internal_config=mock_internal_config,
        )

        with patch(
            "tavern._core.tincture.get_wrapped_response_function",
            return_value=lambda _: None,
        ) as call_mock:
            t = get_stage_tinctures(stage, example, global_cfg)

        t.start_tinctures(stage)
        t.end_tinctures(stage, None)

        # 1 test + 1 stage + 1 global = 3 total
        assert call_mock.call_count == 3

    def test_global_tinctures_none(self, example):
        """Test that passing None for global_cfg works (no global tinctures)"""
        stage = example["stages"][0]
        example["tinctures"] = [{"function": "test_func"}]

        with patch(
            "tavern._core.tincture.get_wrapped_response_function",
            return_value=lambda _: None,
        ) as call_mock:
            t = get_stage_tinctures(stage, example, None)

        t.start_tinctures(stage)
        t.end_tinctures(stage, None)

        assert call_mock.call_count == 1

    def test_global_tinctures_none_value(self, example, mock_internal_config):
        """Test that global_cfg with tinctures=None works (no global tinctures)"""
        stage = example["stages"][0]
        example["tinctures"] = [{"function": "test_func"}]
        global_cfg = make_test_config(
            tinctures=None, mock_internal_config=mock_internal_config
        )

        with patch(
            "tavern._core.tincture.get_wrapped_response_function",
            return_value=lambda _: None,
        ) as call_mock:
            t = get_stage_tinctures(stage, example, global_cfg)

        t.start_tinctures(stage)
        t.end_tinctures(stage, None)

        assert call_mock.call_count == 1

    def test_tincture_execution_order(self, example, mock_internal_config):
        """Test that tinctures are executed in order: test → stage → global"""
        stage = example["stages"][0]
        example["tinctures"] = [{"function": "test_func"}]
        stage["tinctures"] = [{"function": "stage_func"}]
        global_cfg = make_test_config(
            tinctures=[{"function": "global_func"}],
            mock_internal_config=mock_internal_config,
        )

        call_order = []

        def mock_wrapper(func_spec):
            name = func_spec["function"]

            def wrapper(stage):
                call_order.append(name)

            return wrapper

        with patch(
            "tavern._core.tincture.get_wrapped_response_function",
            side_effect=mock_wrapper,
        ):
            t = get_stage_tinctures(stage, example, global_cfg)

        t.start_tinctures(stage)
        t.end_tinctures(stage, None)

        # Verify order: test, stage, global
        assert call_order == ["test_func", "stage_func", "global_func"]
