import logging
import os
import tempfile

import pytest

logger = logging.getLogger(__name__)

name = None


@pytest.fixture(autouse=True)
def setup_logging():
    logging.basicConfig(level=logging.INFO)


def pytest_tavern_beta_after_every_response(expected, response):
    global name
    logging.debug(expected)
    logging.debug(response)
    with open(name, "a") as tfile:
        tfile.write("abc\n")


@pytest.fixture(autouse=True)
def after_check_result():
    """Create a temporary file for the duration of the test, and make sure the above hook was called"""
    global name
    with tempfile.NamedTemporaryFile(delete=False) as tfile:
        try:
            tfile.close()

            name = tfile.name
            yield

            with open(tfile.name) as opened:
                contents = opened.readlines()
                assert len(contents) == 2
                assert all(i.strip() == "abc" for i in contents)

        finally:
            os.remove(tfile.name)
