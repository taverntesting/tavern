import logging.config
import os

import pytest
import yaml

from tavern._core.internal.testutil import enable_default_tavern_extensions


@pytest.fixture(scope="function", autouse=True)
def run_all():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(current_dir, "logging.yaml"), "r") as spec_file:
        settings = yaml.load(spec_file, Loader=yaml.SafeLoader)
        logging.config.dictConfig(settings)


@pytest.fixture(scope="session", autouse=True)
def set_plugins():
    enable_default_tavern_extensions()
