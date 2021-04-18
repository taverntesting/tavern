import copy
from unittest.mock import Mock

import pytest

from tavern.plugins import load_plugins
from tavern.util.strict_util import StrictLevel

_includes = {
    "variables": {
        "request": {"prefix": "www.", "url": "google.com"},
        "test_auth_token": "abc123",
        "code": "def456",
        "callback_url": "www.yahoo.co.uk",
        "request_topic": "/abc",
    },
    "backends": {"mqtt": "paho-mqtt", "http": "requests"},
    "strict": StrictLevel.all_on(),
    "tavern_internal": {"pytest_hook_caller": Mock()},
}


@pytest.fixture(scope="function", name="includes")
def fix_example_includes():
    return copy.deepcopy(_includes)


@pytest.fixture(scope="session", autouse=True)
def initialise_plugins():
    load_plugins(_includes)
