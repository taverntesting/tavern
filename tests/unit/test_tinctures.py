from unittest.mock import patch

import pytest

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
