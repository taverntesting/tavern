"""Tests for the per-stage 'if' and 'retry_until' starlark expressions"""

import dataclasses
import unittest.mock
from collections.abc import Mapping
from unittest.mock import Mock, patch

import pytest
import requests

from tavern._core import exceptions
from tavern._core.pytest.config import TestConfig
from tavern._core.run import run_test
from tavern._core.testhelpers import retry


def _run_test(
    stage: Mapping, test_block_config: TestConfig, run_mock: unittest.mock.Mock
) -> bool:
    """runs the test and returns whether the stage was run or not"""

    full_test = {
        "test_name": "A test with a single stage",
        "stages": [stage],
    }

    run_test("test_file_name", full_test, test_block_config)

    return run_mock.called


class TestIfStage:
    @pytest.fixture(autouse=True)
    def run_mock(self):
        with patch("tavern._core.run._TestRunner.run_stage") as run_mock:
            yield run_mock

    @pytest.fixture(scope="function")
    def stage(self):
        return {
            "name": "test stage",
            "request": {"url": "https://example.com", "method": "GET"},
            "response": {"status_code": 200},
        }

    @pytest.fixture
    def test_block_config(self, includes):
        return dataclasses.replace(
            includes,
            variables={"env_vars": {}},
            experimental_starlark_pipeline=True,
        )

    def test_if_true_runs_stage(self, stage, test_block_config, run_mock):
        stage["if"] = "1 < 2"
        assert _run_test(stage, test_block_config, run_mock) is True

    def test_if_false_skips_stage(self, stage, test_block_config, run_mock):
        stage["if"] = "1 > 2"
        assert _run_test(stage, test_block_config, run_mock) is False

    def test_if_uses_saved_variable(self, stage, test_block_config, run_mock):
        stage["if"] = "var_x > 2"
        test_block_config.variables.update({"var_x": 3})

        assert _run_test(stage, test_block_config, run_mock) is True

    def test_if_uses_saved_variable_false(self, stage, test_block_config, run_mock):
        stage["if"] = "var_x > 2"
        test_block_config.variables.update({"var_x": 1})

        assert _run_test(stage, test_block_config, run_mock) is False

    def test_if_undefined_variable(self, stage, test_block_config, run_mock):
        stage["if"] = "not_saved_yet == 1"

        with pytest.raises(exceptions.EvalError):
            _run_test(stage, test_block_config, run_mock)

    def test_if_non_bool_result(self, stage, test_block_config, run_mock):
        stage["if"] = "'a string'"

        with pytest.raises(exceptions.EvalError):
            _run_test(stage, test_block_config, run_mock)

    def test_if_requires_experimental_flag(self, stage, test_block_config, run_mock):
        stage["if"] = "1 < 2"
        test_block_config = dataclasses.replace(
            test_block_config, experimental_starlark_pipeline=False
        )

        with pytest.raises(exceptions.UnexpectedKeysError):
            _run_test(stage, test_block_config, run_mock)


def _mock_response(body, status_code=200):
    response = Mock(spec=requests.Response)
    response.status_code = status_code
    response.headers = {"Content-Type": "application/json"}
    response.json.return_value = body
    response.cookies = {}
    response.content = b"{}"
    return response


def _stage_failure(body, status_code=200):
    """A stage which failed verification, but which did get a response back"""
    error = exceptions.TestFailError("stage did not verify")
    error.response = _mock_response(body, status_code)
    return error


class TestRetryUntil:
    @pytest.fixture
    def test_block_config(self, includes):
        return dataclasses.replace(
            includes,
            variables={"env_vars": {}},
            experimental_starlark_pipeline=True,
        )

    @pytest.fixture
    def stage(self):
        return {
            "name": "test stage",
            "max_retries": 3,
            "retry_until": "response.body['status'] == 'ready'",
        }

    def test_not_evaluated_when_stage_passes(self, stage, test_block_config):
        """A stage which passes is finished - retry_until is not consulted at all,
        even though it would have been false"""
        response = _mock_response({"status": "pending"})
        inner = Mock(return_value=response)

        assert retry(stage, test_block_config)(inner)() is response
        assert inner.call_count == 1

    def test_stops_when_retry_until_is_true(self, stage, test_block_config):
        """The stage keeps failing, but retry_until eventually becomes true"""
        failures = [
            _stage_failure({"status": "pending"}),
            _stage_failure({"status": "pending"}),
            _stage_failure({"status": "ready"}),
        ]
        inner = Mock(side_effect=failures)

        assert retry(stage, test_block_config)(inner)() is failures[-1].response
        assert inner.call_count == 3

    def test_stops_immediately_when_retry_until_is_true(self, stage, test_block_config):
        inner = Mock(side_effect=_stage_failure({"status": "ready"}))

        retry(stage, test_block_config)(inner)()
        assert inner.call_count == 1

    def test_fails_after_exhausting_retries(self, stage, test_block_config):
        inner = Mock(
            side_effect=lambda: (_ for _ in ()).throw(
                _stage_failure({"status": "pending"})
            )
        )

        with pytest.raises(exceptions.TestFailError) as exc_info:
            retry(stage, test_block_config)(inner)()

        # max_retries = 3 means 4 attempts in total
        assert inner.call_count == 4
        assert "retry_until" in str(exc_info.value)

    def test_not_evaluated_without_a_response(self, stage, test_block_config):
        """If the request itself failed there is no response to inspect, so just retry"""
        inner = Mock(
            side_effect=[
                exceptions.TestFailError("no response at all"),
                _mock_response({"status": "pending"}),
            ]
        )

        retry(stage, test_block_config)(inner)()
        assert inner.call_count == 2

    def test_delay_after_between_attempts(self, stage, test_block_config):
        stage["delay_after"] = 0.01
        inner = Mock(
            side_effect=[
                _stage_failure({"status": "pending"}),
                _stage_failure({"status": "ready"}),
            ]
        )

        with patch("tavern._core.testhelpers.time.sleep") as sleep_mock:
            retry(stage, test_block_config)(inner)()

        sleep_mock.assert_called_once_with(0.01)

    def test_uses_test_variables(self, stage, test_block_config):
        stage["retry_until"] = "response.body['status'] == expected_status"
        test_block_config.variables["expected_status"] = "ready"
        inner = Mock(side_effect=_stage_failure({"status": "ready"}))

        retry(stage, test_block_config)(inner)()
        assert inner.call_count == 1

    def test_uses_status_code(self, stage, test_block_config):
        stage["retry_until"] = "response.status_code == 201"
        inner = Mock(
            side_effect=[
                _stage_failure({}, status_code=503),
                _stage_failure({}, status_code=201),
            ]
        )

        retry(stage, test_block_config)(inner)()
        assert inner.call_count == 2

    def test_without_max_retries_is_an_error(self, stage, test_block_config):
        del stage["max_retries"]

        with pytest.raises(exceptions.InvalidRetryException):
            retry(stage, test_block_config)

    def test_requires_experimental_flag(self, stage, test_block_config):
        test_block_config = dataclasses.replace(
            test_block_config, experimental_starlark_pipeline=False
        )
        inner = Mock(side_effect=_stage_failure({"status": "ready"}))

        with pytest.raises(exceptions.UnexpectedKeysError):
            retry(stage, test_block_config)(inner)()
