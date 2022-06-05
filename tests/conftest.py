import logging.config
import os

import pytest
import yaml


@pytest.fixture(scope="function", autouse=True)
def run_all():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(current_dir, "logging.yaml"), "r") as spec_file:
        settings = yaml.load(spec_file, Loader=yaml.SafeLoader)
        logging.config.dictConfig(settings)
