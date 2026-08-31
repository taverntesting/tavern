import logging
import os
from collections.abc import Iterable

import pytest
from box import Box
from server import run_in_background

from tavern._core import exceptions

if not os.environ.get("TAVERN_INTEGRATION_ALLOW_COLLECT"):
    # Plain top-level pytest: run the yaml suite only via the pytester runner
    # (subprocess), never in-process — tavern patches the yaml parser globally
    # and the suite needs --tavern-global-cfg and a running server.
    collect_ignore_glob = ["test_*.tavern.yaml"]
else:
    # tox-integration generic/noextra (docker server on port 5003) or the
    # pytester subprocess: yaml files run directly, so the runner must not also
    # run (it would run the whole suite a second time).
    collect_ignore = ["test_run_integration_suite.py"]


@pytest.fixture(scope="session")
def integration_server():
    """Base URL of the flask server from server.py, running in a background
    thread on a random port (one server per pytest-xdist worker)."""
    with run_in_background() as port:
        yield f"http://localhost:{port}"


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
    return os.environ.get("TEST_HOST", "http://localhost:5003") + "/echo"


@pytest.fixture(scope="session", autouse=True, name="autouse_thing_named")
def second(autouse_thing):
    return autouse_thing


@pytest.fixture(scope="function")
def tavern_include_env(tmp_path_factory):
    """Create a temporary directory with a test file and set TAVERN_INCLUDE so
    tavern can resolve files in it."""

    tmp_dir = tmp_path_factory.mktemp("tavern_include")
    include_file = tmp_dir / "tavern_include_data.txt"
    include_file.write_text("OK")

    old_value = os.environ.get("TAVERN_INCLUDE")
    os.environ["TAVERN_INCLUDE"] = str(tmp_dir)

    yield

    if old_value is not None:
        os.environ["TAVERN_INCLUDE"] = old_value
    else:
        os.environ.pop("TAVERN_INCLUDE", None)


def pytest_tavern_beta_before_every_request(request_args: Box):
    logging.info("Making request: %s", request_args)

    if not isinstance(request_args.get("json"), Iterable):
        return

    if "PLEASE ADD DATA HERE" in request_args["json"]:
        request_args["json"] = {"value": 123}

    if "PLEASE FAIL THIS TEST" in request_args["json"]:
        raise exceptions.TestFailError("I was asked to fail this test")
