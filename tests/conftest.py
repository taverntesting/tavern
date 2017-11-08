import pytest
import os
import yaml
import logging.config


@pytest.fixture(scope="function", autouse=True)
def run_all():
    current_dir = os.path.dirname(os.path.abspath(__file__))
    with open(os.path.join(current_dir, "logging.yaml"), "r") as spec_file:
        settings = yaml.load(spec_file)
        logging.config.dictConfig(settings)


@pytest.fixture(name="includes")
def fix_example_includes():
    includes = {
        "variables": {
            "request_url": "www.google.com",
            "test_auth_token": "abc123",
            "code": "def456",
            "callback_url": "www.yahoo.co.uk",
        }
    }

    return includes.copy()
