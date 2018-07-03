import pytest


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
    response = (yield "hello")
