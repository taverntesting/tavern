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
from tavern._core.starlark.stage_registry import StageRegistry
from tavern._core.starlark.starlark_env import (
    StageResponse,
    StarlarkPipelineRunner,
    _wrap_callable,
)
from tavern._core.tincture import Tinctures


@pytest.fixture
def mock_test_runner(mock_response):
    runner = Mock(spec=_TestRunner)
    runner.wrapped_run_stage = Mock(return_value=mock_response)
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
    """Tests for the _wrap_callable decorator."""

    def test_wrap_callable_converts_args_to_starlark(self):
        """Test that _wrap_callable converts Python args to starlark format."""

        @_wrap_callable
        def add(a, b):
            return a + b

        # The decorator wraps the function, converting arguments
        result = add(1, 2)
        assert result == 3

    def test_wrap_callable_converts_kwargs_to_starlark(self):
        """Test that _wrap_callable converts Python kwargs to starlark format."""

        @_wrap_callable
        def format_url(base, path=""):
            return f"{base}{path}"

        result = format_url("http://example.com", path="/api")
        assert result == "http://example.com/api"

    def test_wrap_callable_converts_return_to_starlark(self):
        """Test that _wrap_callable converts return value to starlark format."""

        @_wrap_callable
        def get_dict():
            return {"key": "value"}

        result = get_dict()
        assert result == {"key": "value"}

    def test_wrap_callable_converts_opaque_return_to_starlark(self):
        """Test that _wrap_callable converts opaque return value to starlark format."""

        class _boobllb:
            pass

        @_wrap_callable
        def get_dict():
            return _boobllb

        result = get_dict()
        assert isinstance(result, starlark.OpaquePythonObject)


class TestStageResponseToStarlark:
    """Tests for StageResponse.to_starlark method."""

    def test_to_starlark_success_true(self):
        """Test to_starlark with success=True."""
        response = StageResponse(
            success=True,
            response=None,
            request_vars={"key": "value"},
            stage_name="test_stage",
        )
        result = response.to_starlark()
        assert result["success"] is True
        assert result["request_vars"] == {"key": "value"}
        assert result["stage_name"] == "test_stage"

    def test_to_starlark_success_false(self):
        """Test to_starlark with success=False."""
        response = StageResponse(
            success=False,
            response=None,
            request_vars={},
            stage_name="failed_stage",
        )
        result = response.to_starlark()
        assert result["success"] is False

    def test_from_starlark_roundtrip(self):
        """Test from_starlark creates equivalent object."""
        original = StageResponse(
            success=True,
            response={"status_code": 200},
            request_vars={"token": "abc"},
            stage_name="test",
        )
        starlark_dict = original.to_starlark()
        reconstructed = StageResponse.from_starlark(starlark_dict)
        assert reconstructed.success == original.success
        assert reconstructed.request_vars == original.request_vars
        assert reconstructed.stage_name == original.stage_name


class TestRunStageBinding:
    """Tests for the run_stage function exposed to Starlark."""

    def test_run_stage_binding_success(
        self,
        basic_runner,
        sample_stage,
        mock_test_runner,
    ):
        """Test that run_stage binding returns success response."""
        basic_runner._stage_registry = StageRegistry([sample_stage])
        tinctures = Tinctures([])

        with (
            patch(
                "tavern._core.starlark.starlark_env._TestRunner",
                return_value=mock_test_runner,
            ),
            patch(
                "tavern._core.starlark.starlark_env.get_stage_tinctures",
                return_value=tinctures,
            ),
        ):
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
        from tavern._core import exceptions

        runner = StarlarkPipelineRunner(
            test_path="/test/path.tavern.star",
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

    def test_create_response_struct_with_success(self, fix_test_config):
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

        runner = StarlarkPipelineRunner(
            test_path="/test/path.tavern.star",
            stages=[],
            test_config=fix_test_config,
            sessions={},
        )

        result = runner._create_response_struct(stage_response)

        assert result["success"] is True
        assert result["failed"] is False
        assert result["status_code"] == 200
        assert result["body"] == {"data": "test"}
        assert result["request_vars"] == {"key": "value"}
        assert result["stage_name"] == "success_stage"
        # Verify json() was called
        mock_response.json.assert_called_once()

    def test_create_response_struct_with_failure(self, fix_test_config):
        """Test response struct creation with failed response."""
        stage_response = StageResponse(
            success=False,
            response=None,
            request_vars={},
            stage_name="failed_stage",
        )

        runner = StarlarkPipelineRunner(
            test_path="/test/path.tavern.star",
            stages=[],
            test_config=fix_test_config,
            sessions={},
        )

        result = runner._create_response_struct(stage_response)

        assert result["success"] is False
        assert result["failed"] is True
        assert "stage_name" in result

    def test_create_response_struct_none_response(self, fix_test_config):
        """Test response struct creation when response is None."""
        stage_response = StageResponse(
            success=True,
            response=None,
            request_vars={},
            stage_name="no_response_stage",
        )

        runner = StarlarkPipelineRunner(
            test_path="/test/path.tavern.star",
            stages=[],
            test_config=fix_test_config,
            sessions={},
        )

        result = runner._create_response_struct(stage_response)

        assert result["success"] is True
        assert result["failed"] is False
        # When response is None, status_code should not be in result
        assert "status_code" not in result

    def test_create_response_struct_unsupported_type_raises(self, fix_test_config):
        """Test that unsupported response types raise NotImplementedError."""
        # Use an object that's not requests.Response
        unsupported_response = {"type": "grpc"}

        stage_response = StageResponse(
            success=True,
            response=unsupported_response,
            request_vars={},
            stage_name="grpc_stage",
        )

        runner = StarlarkPipelineRunner(
            test_path="/test/path.tavern.star",
            stages=[],
            test_config=fix_test_config,
            sessions={},
        )

        with pytest.raises(NotImplementedError, match="gRPC, MQTT"):
            runner._create_response_struct(stage_response)


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
            stages=sample_stages,
            test_config=fix_test_config,
            sessions={},
        )
        tinctures = Tinctures([])

        script = """
load("@tavern_helpers.star", "run_stage")
resp = run_stage("get_cookie")
"""

        with (
            patch(
                "tavern._core.starlark.starlark_env._TestRunner",
                return_value=mock_test_runner,
            ),
            patch(
                "tavern._core.starlark.starlark_env.get_stage_tinctures",
                return_value=tinctures,
            ),
        ):
            runner.load_and_run(script)

        # Verify wrapped_run_stage was called
        mock_test_runner.wrapped_run_stage.assert_called_once()

    def test_run_stage_tavern_exception_raises(
        self,
        fix_test_config,
        sample_stage,
    ):
        """Test that TavernException is re-raised when continue_on_fail=False."""
        mock_runner = Mock()
        exc = exceptions.TavernException("Stage failed")
        exc.stage = sample_stage
        mock_runner.wrapped_run_stage = Mock(side_effect=exc)
        tinctures = Tinctures([])

        runner = StarlarkPipelineRunner(
            test_path="/test/path.tavern.star",
            stages=[sample_stage],
            test_config=fix_test_config,
            sessions={},
        )

        with (
            patch(
                "tavern._core.starlark.starlark_env._TestRunner",
                return_value=mock_runner,
            ),
            patch(
                "tavern._core.starlark.starlark_env.get_stage_tinctures",
                return_value=tinctures,
            ),
        ):
            with pytest.raises(exceptions.TavernException):
                runner._run_stage(sample_stage, continue_on_fail=False)

    def test_run_stage_tavern_exception_returns_failed(
        self,
        fix_test_config,
        sample_stage,
    ):
        """Test that TavernException returns failed response when continue_on_fail=True."""
        mock_runner = Mock()
        exc = exceptions.TavernException("Stage failed")
        exc.stage = sample_stage
        mock_runner.wrapped_run_stage = Mock(side_effect=exc)
        tinctures = Tinctures([])

        runner = StarlarkPipelineRunner(
            test_path="/test/path.tavern.star",
            stages=[sample_stage],
            test_config=fix_test_config,
            sessions={},
        )

        with (
            patch(
                "tavern._core.starlark.starlark_env._TestRunner",
                return_value=mock_runner,
            ),
            patch(
                "tavern._core.starlark.starlark_env.get_stage_tinctures",
                return_value=tinctures,
            ),
        ):
            response = runner._run_stage(sample_stage, continue_on_fail=True)

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
            stages=sample_stages,
            test_config=fix_test_config,
            sessions={},
        )
        tinctures = Tinctures([])

        script = """
load("@tavern_helpers.star", "run_stage")
resp = run_stage("get_cookie", extra_vars={"custom_var": "custom_value"})
"""

        with (
            patch(
                "tavern._core.starlark.starlark_env._TestRunner",
                return_value=mock_test_runner,
            ),
            patch(
                "tavern._core.starlark.starlark_env.get_stage_tinctures",
                return_value=tinctures,
            ),
        ):
            runner.load_and_run(script)

        # Verify extra_vars were passed to stage_config (positional arg at index 1)
        call_args = mock_test_runner.wrapped_run_stage.call_args
        stage_config = call_args[0][1]  # Second positional argument
        extra_vars_in_request = stage_config.variables
        assert "custom_var" in extra_vars_in_request
        assert extra_vars_in_request["custom_var"] == "custom_value"

    def test_run_stage_continue_on_fail(
        self,
        fix_test_config,
        sample_stages,
    ):
        """Test that continue_on_fail parameter prevents exception propagation."""
        mock_runner = Mock()
        exc = exceptions.TavernException("Stage failed")
        exc.stage = sample_stages[0]
        mock_runner.wrapped_run_stage = Mock(side_effect=exc)
        tinctures = Tinctures([])

        runner = StarlarkPipelineRunner(
            test_path="/test/path.tavern.star",
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

        with (
            patch(
                "tavern._core.starlark.starlark_env._TestRunner",
                return_value=mock_runner,
            ),
            patch(
                "tavern._core.starlark.starlark_env.get_stage_tinctures",
                return_value=tinctures,
            ),
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
        mock_runner.wrapped_run_stage = Mock(side_effect=exc)
        tinctures = Tinctures([])

        runner = StarlarkPipelineRunner(
            test_path="/test/path.tavern.star",
            stages=sample_stages,
            test_config=fix_test_config,
            sessions={},
        )

        script = """
load("@tavern_helpers.star", "run_stage")
# continue_on_fail is False by default
resp = run_stage("get_cookie")
"""

        with (
            patch(
                "tavern._core.starlark.starlark_env._TestRunner",
                return_value=mock_runner,
            ),
            patch(
                "tavern._core.starlark.starlark_env.get_stage_tinctures",
                return_value=tinctures,
            ),
        ):
            # Should raise StarlarkError (wrapping TavernException)
            with pytest.raises((exceptions.StarlarkError, exceptions.TavernException)):
                runner.load_and_run(script)
