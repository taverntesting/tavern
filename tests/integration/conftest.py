import logging
from collections.abc import Iterable

import pytest
from box import Box

from tavern._core import exceptions


@pytest.fixture
def str_fixture():
    return "abc-fixture-value"


@pytest.fixture(name="yield_str_fixture")
def sdkofsok(str_fixture):
    yield str_fixture


@pytest.fixture(name="yielder")
def bluerhug(request):
    # This doesn't really do anything at the moment. In future it might yield
    # the result or something, but it's a bit difficult to do at the moment.
    yield "hello"


@pytest.fixture(scope="session", autouse=True)
def autouse_thing():
    return "abc"


@pytest.fixture(scope="session", autouse=True)
def fixture_echo_url():
    return "http://localhost:5003/echo"


@pytest.fixture(scope="session", autouse=True, name="autouse_thing_named")
def second(autouse_thing):
    return autouse_thing


def pytest_tavern_beta_before_every_request(request_args: Box):
    logging.info("Making request: %s", request_args)

    if not isinstance(request_args.get("json"), Iterable):
        return

    if "PLEASE ADD DATA HERE" in request_args["json"]:
        request_args["json"] = {"value": 123}

    if "PLEASE FAIL THIS TEST" in request_args["json"]:
        raise exceptions.TestFailError("I was asked to fail this test")
