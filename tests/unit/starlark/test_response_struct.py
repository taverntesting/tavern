from unittest.mock import Mock

import pytest
import requests

from tavern._core.pytest.config import TavernInternalConfig, TestConfig
from tavern._core.starlark.starlark_env import StageResponse, StarlarkPipelineRunner
from tavern._core.strict_util import StrictLevel


@pytest.fixture
def mock_tavern_internal():
    return TavernInternalConfig(pytest_hook_caller=Mock(), backends={})


@pytest.fixture
def mock_test_config(mock_tavern_internal):
    config = Mock(spec=TestConfig)
    config.variables = {}
    config.strict = StrictLevel.all_on()
    config.tavern_internal = mock_tavern_internal
    config.follow_redirects = False
    config.stages = []
    config.tinctures = []
    return config


@pytest.fixture
def mock_response():
    """Create a mock requests.Response for HTTP responses."""
    response = Mock(spec=requests.Response)
    response.status_code = 200
    response.headers = {"Content-Type": "application/json"}
    response.json.return_value = {"foo": "bar"}
    response.cookies = {}
    response.content = b'{"foo": "bar"}'
    return response


class TestStageResponseStruct:
    def test_stage_response_has_status_code_in_response(self):
        response = StageResponse(
            success=True,
            response={"status_code": 200, "body": {"foo": "bar"}},
            request_vars={},
            stage_name="test_stage",
        )
        starlark_obj = response.to_starlark()
        assert "status_code" in starlark_obj["response"]

    def test_stage_response_has_failed_not_in_response(self):
        response = StageResponse(
            success=False,
            response={"status_code": 500, "error": "server error"},
            request_vars={},
            stage_name="test_stage",
        )
        starlark_obj = response.to_starlark()
        assert "failed" not in starlark_obj["response"]

    def test_stage_response_has_success_field(self):
        response = StageResponse(
            success=True,
            response={"status_code": 200},
            request_vars={},
            stage_name="test_stage",
        )
        starlark_obj = response.to_starlark()
        assert "success" in starlark_obj

    def test_stage_response_has_body_in_response(self):
        response = StageResponse(
            success=True,
            response={"status_code": 200, "body": {"data": "test"}},
            request_vars={},
            stage_name="test_stage",
        )
        starlark_obj = response.to_starlark()
        assert "response" in starlark_obj

    def test_stage_response_has_request_vars(self):
        response = StageResponse(
            success=True,
            response={"status_code": 200},
            request_vars={"var": "value"},
            stage_name="test_stage",
        )
        starlark_obj = response.to_starlark()
        assert "request_vars" in starlark_obj


@pytest.fixture
def basic_runner(mock_test_config):
    return StarlarkPipelineRunner(
        test_path="/fake/path",
        stages=[],
        test_config=mock_test_config,
        sessions={},
    )


class TestCreateResponseStruct:
    def test_create_response_dict_has_status_code(self, basic_runner, mock_response):
        response = StageResponse(
            success=True,
            response=mock_response,
            request_vars={},
            stage_name="test_stage",
        )
        result = basic_runner._create_response_struct(response)
        assert "status_code" in result
        assert result["status_code"] == 200

    def test_create_response_dict_has_failed(self, basic_runner):
        response = StageResponse(
            success=False,
            response=None,
            request_vars={},
            stage_name="test_stage",
        )
        result = basic_runner._create_response_struct(response)
        assert "failed" in result
        assert result["failed"] is True

    def test_create_response_dict_has_success(self, basic_runner):
        response = StageResponse(
            success=True,
            response=None,
            request_vars={},
            stage_name="test_stage",
        )
        result = basic_runner._create_response_struct(response)
        assert "success" in result
        assert result["success"] is True

    def test_create_response_dict_has_body(self, basic_runner, mock_response):
        response = StageResponse(
            success=True,
            response=mock_response,
            request_vars={},
            stage_name="test_stage",
        )
        result = basic_runner._create_response_struct(response)
        assert "body" in result

    def test_create_response_dict_has_request_vars(self, basic_runner):
        response = StageResponse(
            success=True,
            response=None,
            request_vars={"token": "abc"},
            stage_name="test_stage",
        )
        result = basic_runner._create_response_struct(response)
        assert "request_vars" in result

    def test_create_response_dict_has_stage_name(self, basic_runner):
        response = StageResponse(
            success=True,
            response=None,
            request_vars={},
            stage_name="my_stage",
        )
        result = basic_runner._create_response_struct(response)
        assert "stage_name" in result
        assert result["stage_name"] == "my_stage"
