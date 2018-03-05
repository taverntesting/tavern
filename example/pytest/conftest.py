import pytest


@pytest.fixture
def number():
    return 123


@pytest.fixture
def double(number):
    return number * 2
