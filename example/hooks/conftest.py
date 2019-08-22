import logging

import pytest

logger = logging.getLogger(__name__)


@pytest.fixture(autouse=True)
def setup_logging():
    logging.basicConfig(level=logging.INFO)


def pytest_tavern_after_every_response(expected, response):
    logging.critical(expected)
    logging.critical(response)
    assert 0
