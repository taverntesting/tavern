from unittest.mock import Mock

import pytest
import requests

from tavern._core.pytest.config import TavernInternalConfig, TestConfig
from tavern._core.starlark.starlark_env import StarlarkPipelineRunner
from tavern._core.strict_util import StrictLevel


@pytest.fixture
def mock_tavern_internal():
    return TavernInternalConfig(pytest_hook_caller=Mock(), backends={})


@pytest.fixture
def mock_test_config(mock_tavern_internal):
    config = Mock(spec=TestConfig)
    config.variables = {"base_url": "http://test.example.com", "tavern": Mock()}
    config.strict = StrictLevel.all_on()
    config.tavern_internal = mock_tavern_internal
    config.follow_redirects = False
    config.stages = []
    config.tinctures = []
    config_copy = Mock(spec=TestConfig)
    config_copy.variables = {"base_url": "http://test.example.com", "tavern": Mock()}
    config_copy.strict = StrictLevel.all_on()
    config_copy.tavern_internal = mock_tavern_internal
    config_copy.follow_redirects = False
    config_copy.stages = []
    config_copy.tinctures = []
    config_copy.with_strictness = Mock(return_value=config_copy)
    config.with_new_variables = Mock(return_value=config_copy)
    config.with_strictness = Mock(return_value=config)
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
