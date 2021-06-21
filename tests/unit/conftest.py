from unittest.mock import Mock

import pytest
import stevedore

from tavern.plugins import load_plugins as plugin_loader
from tavern._plugins.rest.tavernhook import TavernRestPlugin
from tavern._plugins.mqtt import tavernhook as TavernMQTTPlugin

import tavern
import tavern._plugins
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

    plugin_loader.plugins = [
        extension(
            "requests",
            TavernRestPlugin,
        ),
        extension(
            "paho-mqtt",
            TavernMQTTPlugin,
        ),
    ]
