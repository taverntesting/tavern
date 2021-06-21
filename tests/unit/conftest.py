from unittest.mock import Mock

import pytest
import stevedore

import tavern
from tavern.util.strict_util import StrictLevel


@pytest.fixture(name="includes")
def fix_example_includes():
    includes = {
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

    return includes.copy()


@pytest.fixture(scope="session", autouse=True)
def set_plugins():
    def extension(name, point):
        return stevedore.extension.Extension(name, point, point, point)

    tavern.plugins.load_plugins.plugins = [
        extension(
            "requests",
            tavern._plugins.rest.tavernhook.TavernRestPlugin,
        ),
        extension(
            "paho-mqtt",
            tavern._plugins.mqtt.tavernhook,
        ),
    ]
