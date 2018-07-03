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
def str_fixture():
    return "abc-fixture-value"


@pytest.fixture(name="yield_str_fixture")
def sdkofsok(str_fixture):
    yield str_fixture


@pytest.fixture(name="yielder")
def bluerhug():
    # This doesn't really do anything at the moment. In future it might yield
    # the result or something, but it's a bit difficult to do at the moment.
    response = (yield "hello")
