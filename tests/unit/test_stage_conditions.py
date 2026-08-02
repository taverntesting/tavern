"""Tests for the per-stage 'if', 'retry_until' and 'fail_if' starlark expressions"""

import dataclasses
import unittest.mock
from collections.abc import Mapping
from unittest.mock import Mock, create_autospec, patch

import pytest
import requests

from tavern._core import exceptions
from tavern._core.pytest.config import TestConfig
from tavern._core.run import _TestRunner, run_test
from tavern._core.strict_util import StrictLevel
from tavern._core.testhelpers import retry
from tavern._core.tincture import Tinctures
from tavern.request import BaseRequest
from tavern.response import BaseResponse


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
        stage["if"] = "{var_x} > 2"
        test_block_config.variables.update({"var_x": 3})

        assert _run_test(stage, test_block_config, run_mock) is True

    def test_if_uses_saved_variable_false(self, stage, test_block_config, run_mock):
        stage["if"] = "{var_x} > 2"
        test_block_config.variables.update({"var_x": 1})

        assert _run_test(stage, test_block_config, run_mock) is False

    def test_if_undefined_variable(self, stage, test_block_config, run_mock):
        stage["if"] = "{not_saved_yet} == 1"

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

    @pytest.mark.parametrize("terminal_status", ["SUCCESS", "FAILED"])
    def test_stops_on_any_terminal_state(
        self, stage, test_block_config, terminal_status
    ):
        """Poll a long running job until it finishes, whether it succeeded or not

        https://github.com/taverntesting/tavern/issues/751
        """
        stage["retry_until"] = (
            "response.body['status'] == 'SUCCESS'"
            " or response.body['status'] == 'FAILED'"
        )
        stage["max_retries"] = 5
        failures = [
            _stage_failure({"status": "IN_PROGRESS"}),
            _stage_failure({"status": "IN_PROGRESS"}),
            _stage_failure({"status": terminal_status}),
        ]
        inner = Mock(side_effect=failures)

        assert retry(stage, test_block_config)(inner)() is failures[-1].response
        assert inner.call_count == 3

    def test_never_reaching_a_terminal_state_fails(self, stage, test_block_config):
        stage["retry_until"] = (
            "response.body['status'] == 'SUCCESS'"
            " or response.body['status'] == 'FAILED'"
        )
        stage["max_retries"] = 2
        inner = Mock(
            side_effect=lambda: (_ for _ in ()).throw(
                _stage_failure({"status": "IN_PROGRESS"})
            )
        )

        with pytest.raises(exceptions.TestFailError):
            retry(stage, test_block_config)(inner)()

        assert inner.call_count == 3

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
        stage["retry_until"] = "response.body['status'] == '{expected_status}'"
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


def _stage_callable():
    """The signature of the function that 'retry' wraps, used as a Mock spec"""


def _mock_stage_callable(**kwargs) -> Mock:
    """A mock of the function that 'retry' wraps

    This is autospecced rather than a plain Mock because the retry wrapper calls
    functools.wraps on it, which needs the real function attributes.
    """
    return create_autospec(_stage_callable, **kwargs)


def _run_stage(stage, test_block_config, response, *, verify_error=None):
    """Run a single stage, mocking out everything to do with actually making a request

    Args:
        stage: the stage to run
        test_block_config: config for the test
        response: what the 'request' should return
        verify_error: if given, an exception raised when verifying the response
    """

    verifier = Mock(spec=BaseResponse)
    if verify_error is not None:
        verifier.verify.side_effect = verify_error
    else:
        verifier.verify.return_value = {}

    request = Mock(spec=BaseRequest)
    request.request_vars = {}
    request.run.return_value = response

    runner = _TestRunner(
        default_global_strictness=StrictLevel.all_on(),
        sessions={},
        test_block_config=test_block_config,
        test_spec={"test_name": "a test", "stages": [stage]},
    )

    with (
        patch("tavern._core.run.attach_stage_content"),
        patch("tavern._core.run.call_hook"),
        patch("tavern._core.run.get_request_type", return_value=request),
        patch("tavern._core.run.get_expected", return_value={}),
        patch("tavern._core.run.get_verifiers", return_value={"response": [verifier]}),
    ):
        return runner.wrapped_run_stage(stage, test_block_config, Mock(spec=Tinctures))


class TestFailIf:
    @pytest.fixture
    def test_block_config(self, includes):
        return dataclasses.replace(
            includes,
            variables={"env_vars": {}, "tavern": {}},
            experimental_starlark_pipeline=True,
        )

    @pytest.fixture
    def stage(self):
        return {
            "name": "test stage",
            "request": {"url": "https://example.com", "method": "GET"},
            "response": {"status_code": 200},
            "fail_if": "response.body['status'] == 'FAILED'",
        }

    def test_passing_stage_with_false_expression(self, stage, test_block_config):
        response = _mock_response({"status": "SUCCESS"})

        assert _run_stage(stage, test_block_config, response) is response

    def test_passing_stage_with_true_expression(self, stage, test_block_config):
        """The response block matched, but the stage is a failure anyway"""
        response = _mock_response({"status": "FAILED"})

        with pytest.raises(exceptions.FailIfError) as exc_info:
            _run_stage(stage, test_block_config, response)

        assert "fail_if" in str(exc_info.value)

    def test_failing_stage_with_true_expression(self, stage, test_block_config):
        response = _mock_response({"status": "FAILED"})

        with pytest.raises(exceptions.FailIfError):
            _run_stage(
                stage,
                test_block_config,
                response,
                verify_error=exceptions.TestFailError("stage did not verify"),
            )

    def test_failing_stage_with_false_expression(self, stage, test_block_config):
        """The normal failure is unaffected by a 'fail_if' which was false"""
        response = _mock_response({"status": "IN_PROGRESS"})

        with pytest.raises(exceptions.TestFailError) as exc_info:
            _run_stage(
                stage,
                test_block_config,
                response,
                verify_error=exceptions.TestFailError("stage did not verify"),
            )

        assert not isinstance(exc_info.value, exceptions.FailIfError)

    def test_uses_test_variables(self, stage, test_block_config):
        stage["fail_if"] = "response.body['status'] == '{bad_status}'"
        test_block_config.variables["bad_status"] = "FAILED"

        with pytest.raises(exceptions.FailIfError):
            _run_stage(stage, test_block_config, _mock_response({"status": "FAILED"}))

    def test_knows_the_stage_failed(self, stage, test_block_config):
        stage["fail_if"] = "response.failed"

        with pytest.raises(exceptions.FailIfError):
            _run_stage(
                stage,
                test_block_config,
                _mock_response({"status": "SUCCESS"}),
                verify_error=exceptions.TestFailError("stage did not verify"),
            )

    def test_knows_the_stage_passed(self, stage, test_block_config):
        stage["fail_if"] = "response.failed"
        response = _mock_response({"status": "SUCCESS"})

        assert _run_stage(stage, test_block_config, response) is response

    def test_non_bool_result(self, stage, test_block_config):
        stage["fail_if"] = "response.body['status']"

        with pytest.raises(exceptions.EvalError):
            _run_stage(stage, test_block_config, _mock_response({"status": "FAILED"}))

    def test_must_be_a_string(self, stage, test_block_config):
        stage["fail_if"] = True

        with pytest.raises(exceptions.BadSchemaError):
            _run_stage(stage, test_block_config, _mock_response({"status": "FAILED"}))

    def test_requires_experimental_flag(self, stage, test_block_config):
        test_block_config = dataclasses.replace(
            test_block_config, experimental_starlark_pipeline=False
        )

        with pytest.raises(exceptions.UnexpectedKeysError):
            _run_stage(stage, test_block_config, _mock_response({"status": "FAILED"}))

    def test_is_not_retried(self, stage, test_block_config):
        """A stage which hit its 'fail_if' is in a terminal state, so don't retry it

        https://github.com/taverntesting/tavern/issues/751
        """
        stage["max_retries"] = 5
        inner = _mock_stage_callable(
            side_effect=exceptions.FailIfError("fail_if was true")
        )

        with pytest.raises(exceptions.FailIfError):
            retry(stage, test_block_config)(inner)()

        assert inner.call_count == 1

    def test_takes_priority_over_retry_until(self, stage, test_block_config):
        """Both keys are evaluated, but 'fail_if' is checked while running the stage so
        it never reaches the 'retry_until' handling in the retry wrapper"""
        stage["max_retries"] = 5
        stage["retry_until"] = "True"
        inner = _mock_stage_callable(
            side_effect=exceptions.FailIfError("fail_if was true")
        )

        with pytest.raises(exceptions.FailIfError):
            retry(stage, test_block_config)(inner)()

        assert inner.call_count == 1
