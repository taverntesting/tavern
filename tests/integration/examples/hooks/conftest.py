import logging
import os
import tempfile

import pytest

logger = logging.getLogger(__name__)

name = None


def pytest_tavern_beta_after_every_response(expected, response):
    """Called for every response in the test"""
    global name
    if name is not None:
        logging.debug(expected)
        logging.debug(response)
        with open(name, "a") as tfile:
            tfile.write("abc\n")


@pytest.fixture(autouse=True)
def after_check_result(request):
    """Create a temporary file for the duration of the test, and make sure the above hook was called"""

    # Only check this example test
    if not request.node.spec["test_name"] == "Hook example":
        return

    global name
    with tempfile.NamedTemporaryFile(delete=False) as tfile:
        try:
            tfile.close()

            name = tfile.name
            yield
            name = None

            with open(tfile.name, "r") as opened:
                contents = opened.readlines()
                assert len(contents) == 2
                assert all(i.strip() == "abc" for i in contents)

        finally:
            os.remove(tfile.name)
