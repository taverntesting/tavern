import copy
from unittest.mock import Mock

import pytest

from tavern._core.plugins import load_plugins
from tavern._core.pytest.config import TavernInternalConfig, TestConfig
from tavern._core.strict_util import StrictLevel

_includes = TestConfig(
    variables={
        "request": {"prefix": "www.", "url": "google.com"},
        "test_auth_token": "abc123",
        "code": "def456",
        "callback_url": "www.yahoo.co.uk",
        "request_topic": "/abc",
    },
    strict=StrictLevel.all_on(),
    tavern_internal=TavernInternalConfig(
        pytest_hook_caller=Mock(),
        backends={"mqtt": "paho-mqtt", "http": "requests"},
    ),
    follow_redirects=False,
    stages=[],
)


@pytest.fixture(scope="function", name="includes")
def fix_example_includes():
    return copy.deepcopy(_includes)


@pytest.fixture(scope="session", autouse=True)
def initialise_plugins():
    load_plugins(_includes)
