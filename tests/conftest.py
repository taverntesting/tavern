import logging.config
import os

import pytest
import stevedore
import yaml

import tavern
import tavern._plugins.mqtt.tavernhook as mqtt_plugin
from tavern._plugins.rest.tavernhook import TavernRestPlugin as rest_plugin


@pytest.fixture(scope="function", autouse=True)
def run_all():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(current_dir, "logging.yaml")) as spec_file:
        settings = yaml.load(spec_file, Loader=yaml.SafeLoader)
        logging.config.dictConfig(settings)


@pytest.fixture(scope="session", autouse=True)
def set_plugins():
    def extension(name, point):
        return stevedore.extension.Extension(name, point, point, point)

    tavern._core.plugins.load_plugins.plugins = [
        extension(
            "requests",
            rest_plugin,
        ),
        extension(
            "paho-mqtt",
            mqtt_plugin,
        ),
    ]
