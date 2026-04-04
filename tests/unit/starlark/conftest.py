from unittest.mock import Mock

import pytest
import requests

from tavern._core.pytest.config import TavernInternalConfig, TestConfig
from tavern._core.starlark.starlark_env import StarlarkPipelineRunner
from tavern._core.strict_util import StrictLevel


@pytest.fixture
def mock_test_config():
    """Create a real TestConfig object for starlark tests."""
    config = TestConfig(
        variables={"base_url": "http://test.example.com", "tavern": Mock()},
        strict=StrictLevel.all_on(),
        follow_redirects=False,
        stages=[],
        tavern_internal=TavernInternalConfig(pytest_hook_caller=Mock(), backends={}),
    )
    return config


@pytest.fixture
def mock_response():
    response = Mock(spec=requests.Response)
    response.status_code = 200
    response.headers = {"Content-Type": "application/json"}
    response.json.return_value = {"result": "success"}
    response.cookies = {}
    response.content = b'{"result": "success"}'
    return response


@pytest.fixture
def basic_runner(mock_test_config):
    return StarlarkPipelineRunner(
        test_path="/test/path.tavern.star",
        stages=[],
        test_config=mock_test_config,
        sessions={},
    )
