"""Unit tests for the starlark_env module.

These tests verify the StarlarkPipelineRunner and related functionality,
including run_stage behavior and extra_vars formatting.
"""

from unittest.mock import Mock, patch

import pytest
import requests
import starlark

from tavern._core import exceptions
from tavern._core.run import _TestRunner
from tavern._core.starlark.builtins import wrap_callable
from tavern._core.starlark.stage_registry import StageRegistry
from tavern._core.starlark.starlark_env import (
    StageResponse,
    StarlarkPipelineRunner,
)
from tavern._core.strict_util import StrictLevel


@pytest.fixture
def mock_test_runner(mock_response):
    runner = Mock(spec=_TestRunner)
    runner.run_stage = Mock(return_value=mock_response)
    return runner


@pytest.fixture
def sample_stage():
    return {
        "id": "test_stage",
        "name": "Test Stage",
        "request": {"url": "http://test.example.com/api", "method": "GET"},
        "response": {"status_code": 200},
    }


@pytest.fixture
def sample_stages():
    return [
        {
            "id": "get_cookie",
            "name": "Get Cookie",
            "request": {"url": "http://test.example.com/cookie", "method": "POST"},
            "response": {"status_code": 200},
        },
        {
            "id": "echo_value",
            "name": "Echo Value",
            "request": {"url": "http://test.example.com/echo", "method": "POST"},
            "response": {"status_code": 201},
        },
    ]


class TestWrapCallable:
    """Tests for the wrap_callable decorator."""

    def test_wrap_callable_converts_args_to_starlark(self):
        """Test that wrap_callable converts Python args to starlark format."""

        @wrap_callable
        def add(a, b):
            return a + b

        # The decorator wraps the function, converting arguments
        result = add(1, 2)
        assert result == 3

    def test_wrap_callable_converts_kwargs_to_starlark(self):
        """Test that wrap_callable converts Python kwargs to starlark format."""

        @wrap_callable
        def format_url(base, path=""):
            return f"{base}{path}"

        result = format_url("http://example.com", path="/api")
        assert result == "http://example.com/api"

    def test_wrap_callable_converts_return_to_starlark(self):
        """Test that wrap_callable converts return value to starlark format."""

        @wrap_callable
        def get_dict():
            return {"key": "value"}

        result = get_dict()
        assert result == {"key": "value"}

    def test_wrap_callable_converts_opaque_return_to_starlark(self):
        """Test that wrap_callable converts opaque return value to starlark format."""

        class _boobllb:
            pass

        @wrap_callable
        def get_dict():
            return _boobllb

        result = get_dict()
        assert isinstance(result, starlark.OpaquePythonObject)


class TestRunStageBinding:
    """Tests for the run_stage function exposed to Starlark."""

    def test_run_stage_binding_success(self, basic_runner, sample_stage):
        """Test that run_stage binding returns success response."""
        basic_runner._stage_registry = StageRegistry([sample_stage])

        result = basic_runner._create_response_struct(
            StageResponse(
                success=True,
                response=Mock(
                    spec=requests.Response,
                    status_code=200,
                    headers={},
                    cookies={},
                ),
                request_vars={},
                stage_name="test_stage",
            )
        )

        assert result["success"] is True
        assert result["failed"] is False

    def test_run_stage_binding_stage_not_found(
        self,
        fix_test_config,
        sample_stages,
    ):
        """Test that requesting nonexistent stage raises StarlarkError."""
        runner = StarlarkPipelineRunner(
            test_path="/test/path.tavern.star",
            test_spec={},
            stages=[],  # Empty registry - no stages
            test_config=fix_test_config,
            sessions={},
        )

        script = """
load("@tavern_helpers.star", "run_stage")
resp = run_stage("nonexistent_stage")
"""

        with pytest.raises(exceptions.StarlarkError):
            runner.load_and_run(script)


class TestCreateResponseStruct:
    """Tests for the _create_response_struct method."""

    def test_create_response_struct_with_success(self, basic_runner):
        """Test response struct creation with successful response."""
        mock_response = Mock(spec=requests.Response)
        mock_response.status_code = 200
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.json.return_value = {"data": "test"}
        mock_response.cookies = {}

        stage_response = StageResponse(
            success=True,
            response=mock_response,
            request_vars={"key": "value"},
            stage_name="success_stage",
        )

        result = basic_runner._create_response_struct(stage_response)

        assert result["success"] is True
        assert result["failed"] is False
        assert result["status_code"] == 200
        assert result["body"] == {"data": "test"}
        assert result["request_vars"] == {"key": "value"}
        assert result["stage_name"] == "success_stage"
        # Verify json() was called
        mock_response.json.assert_called_once()

    def test_create_response_struct_with_failure(self, basic_runner):
        """Test response struct creation with failed response."""
        stage_response = StageResponse(
            success=False,
            response=None,
            request_vars={},
            stage_name="failed_stage",
        )

        result = basic_runner._create_response_struct(stage_response)

        assert result["success"] is False
        assert result["failed"] is True
        assert "stage_name" in result

    def test_create_response_struct_none_response(self, basic_runner):
        """Test response struct creation when response is None."""
        stage_response = StageResponse(
            success=True,
            response=None,
            request_vars={},
            stage_name="no_response_stage",
        )

        result = basic_runner._create_response_struct(stage_response)

        assert result["success"] is True
        assert result["failed"] is False
        # When response is None, status_code should not be in result
        assert "status_code" not in result

    def test_create_response_struct_unsupported_type_raises(self, basic_runner):
        """Test that unsupported response types raise NotImplementedError."""
        # Use an object that's not requests.Response
        unsupported_response = {"type": "grpc"}

        stage_response = StageResponse(
            success=True,
            response=unsupported_response,
            request_vars={},
            stage_name="grpc_stage",
        )

        with pytest.raises(NotImplementedError, match="gRPC, MQTT"):
            basic_runner._create_response_struct(stage_response)


class TestStarlarkExecution:
    """Tests that execute actual Starlark scripts."""

    def test_load_and_run_parses_valid_script(self, basic_runner):
        """Test that a valid Starlark script parses without errors."""
        script = """
def my_func():
    return 42
"""
        # Should not raise
        basic_runner.load_and_run(script)

    def test_load_and_run_invalid_script_raises(self, basic_runner):
        """Test that an invalid Starlark script raises ValueError."""
        script = """
def broken_func(
    # Missing closing parenthesis
"""
        with pytest.raises(ValueError, match="Failed to parse starlark script"):
            basic_runner.load_and_run(script)

    def test_log_function_executes(
        self,
        basic_runner,
        caplog,
    ):
        """Test that log function writes to logger."""
        script = """
load("@tavern_helpers.star", "log")
log("Hello from starlark")
"""
        with caplog.at_level("INFO"):
            basic_runner.load_and_run(script)

        assert "Hello from starlark" in caplog.text

    def test_time_sleep_function_executes(self, basic_runner):
        """Test that time.sleep can be called from Starlark script."""
        import time

        script = """
load("@tavern_helpers.star", "time")
time.sleep(0.01)
"""
        start = time.monotonic()
        basic_runner.load_and_run(script)
        elapsed = time.monotonic() - start

        # Verify that sleep was actually called (should take at least 0.01s)
        assert elapsed >= 0.01

    def test_run_stage_in_script(
        self,
        fix_test_config,
        sample_stages,
        mock_test_runner,
    ):
        """Test that run_stage can be called from Starlark script."""
        runner = StarlarkPipelineRunner(
            test_path="/test/path.tavern.star",
            test_spec={},
            stages=sample_stages,
            test_config=fix_test_config,
            sessions={},
        )

        script = """
load("@tavern_helpers.star", "run_stage")
resp = run_stage("get_cookie")
"""

        with patch(
            "tavern._core.starlark.starlark_env._TestRunner",
            return_value=mock_test_runner,
        ):
            runner.load_and_run(script)

        mock_test_runner.run_stage.assert_called_once()

    def test_run_stage_uses_test_strictness_and_spec(
        self,
        fix_test_config,
        sample_stage,
        mock_test_runner,
    ):
        """Stages run from starlark use the global strictness and the real test block, so that
        'strict', 'max_retries' and tinctures behave as they do in a normal test"""
        strict = StrictLevel.all_off()
        test_config = fix_test_config.with_strictness(strict)
        test_spec = {"test_name": "real test", "strict": False, "stages": []}

        runner = StarlarkPipelineRunner(
            test_path="/test/path.tavern.star",
            test_spec=test_spec,
            stages=[sample_stage],
            test_config=test_config,
            sessions={},
        )

        with patch(
            "tavern._core.starlark.starlark_env._TestRunner",
            return_value=mock_test_runner,
        ) as runner_class:
            runner._run_stage(sample_stage, continue_on_fail=False)

        kwargs = runner_class.call_args.kwargs
        assert kwargs["default_global_strictness"] is strict
        assert kwargs["test_spec"] is test_spec
        mock_test_runner.run_stage.assert_called_once_with(0, sample_stage)

    def test_run_stage_tavern_exception_raises(
        self,
        basic_runner,
        sample_stage,
    ):
        """Test that TavernException is re-raised when continue_on_fail=False."""
        mock_runner = Mock()
        exc = exceptions.TavernException("Stage failed")
        exc.stage = sample_stage
        mock_runner.run_stage = Mock(side_effect=exc)

        with patch(
            "tavern._core.starlark.starlark_env._TestRunner",
            return_value=mock_runner,
        ):
            with pytest.raises(exceptions.TavernException):
                basic_runner._run_stage(sample_stage, continue_on_fail=False)

    def test_run_stage_tavern_exception_returns_failed(
        self,
        basic_runner,
        sample_stage,
    ):
        """Test that TavernException returns failed response when continue_on_fail=True."""
        mock_runner = Mock()
        exc = exceptions.TavernException("Stage failed")
        exc.stage = sample_stage
        mock_runner.run_stage = Mock(side_effect=exc)

        with patch(
            "tavern._core.starlark.starlark_env._TestRunner",
            return_value=mock_runner,
        ):
            response = basic_runner._run_stage(sample_stage, continue_on_fail=True)

        assert response.success is False
        assert response.stage_name == sample_stage["name"]

    def test_run_stage_with_extra_vars(
        self,
        fix_test_config,
        sample_stages,
        mock_test_runner,
    ):
        """Test that extra_vars can be passed to run_stage from Starlark."""
        runner = StarlarkPipelineRunner(
            test_path="/test/path.tavern.star",
            test_spec={},
            stages=sample_stages,
            test_config=fix_test_config,
            sessions={},
        )

        script = """
load("@tavern_helpers.star", "run_stage")
resp = run_stage("get_cookie", extra_vars={"custom_var": "custom_value"})
"""

        with patch(
            "tavern._core.starlark.starlark_env._TestRunner",
            return_value=mock_test_runner,
        ) as runner_class:
            runner.load_and_run(script)

        stage_variables = runner_class.call_args.kwargs["test_block_config"].variables
        assert stage_variables["custom_var"] == "custom_value"
        # extra_vars only apply to the one stage
        assert "custom_var" not in fix_test_config.variables

    def test_run_stage_with_extra_vars_keeps_saved_values(
        self,
        basic_runner,
        fix_test_config,
        sample_stage,
        mock_response,
    ):
        """Values saved by a stage run with extra_vars are available to later stages"""

        def make_runner(**kwargs):
            def save_token(idx, stage):
                kwargs["test_block_config"].variables["token"] = "abc"
                return mock_response

            return Mock(run_stage=save_token)

        with patch(
            "tavern._core.starlark.starlark_env._TestRunner", side_effect=make_runner
        ):
            basic_runner._run_stage(
                sample_stage, continue_on_fail=False, extra_vars={"user": "a"}
            )

        assert fix_test_config.variables["token"] == "abc"
        assert "user" not in fix_test_config.variables

    def test_run_stage_continue_on_fail(
        self,
        fix_test_config,
        sample_stages,
    ):
        """Test that continue_on_fail parameter prevents exception propagation."""
        mock_runner = Mock()
        exc = exceptions.TavernException("Stage failed")
        exc.stage = sample_stages[0]
        mock_runner.run_stage = Mock(side_effect=exc)

        runner = StarlarkPipelineRunner(
            test_path="/test/path.tavern.star",
            test_spec={},
            stages=sample_stages,
            test_config=fix_test_config,
            sessions={},
        )

        script = """
load("@tavern_helpers.star", "run_stage")
# continue_on_fail=True should catch the exception
resp = run_stage("get_cookie", continue_on_fail=True)
# Script should continue without raising
"""

        with patch(
            "tavern._core.starlark.starlark_env._TestRunner",
            return_value=mock_runner,
        ):
            # Should not raise
            runner.load_and_run(script)

    def test_run_stage_failure_propagates(
        self,
        fix_test_config,
        sample_stages,
    ):
        """Test that failed stage propagates exception when continue_on_fail=False."""
        mock_runner = Mock()
        exc = exceptions.TavernException("Stage failed")
        exc.stage = sample_stages[0]
        mock_runner.run_stage = Mock(side_effect=exc)

        runner = StarlarkPipelineRunner(
            test_path="/test/path.tavern.star",
            test_spec={},
            stages=sample_stages,
            test_config=fix_test_config,
            sessions={},
        )

        script = """
load("@tavern_helpers.star", "run_stage")
# continue_on_fail is False by default
resp = run_stage("get_cookie")
"""

        with patch(
            "tavern._core.starlark.starlark_env._TestRunner",
            return_value=mock_runner,
        ):
            # Should raise StarlarkError (wrapping TavernException)
            with pytest.raises((exceptions.StarlarkError, exceptions.TavernException)):
                runner.load_and_run(script)
