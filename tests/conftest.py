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


@pytest.fixture
def abc():
    return "abc-fixture-value"


@pytest.fixture(name="def")
def sdkofsok(abc):
    return abc
