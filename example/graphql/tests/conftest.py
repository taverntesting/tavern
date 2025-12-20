import pytest


@pytest.fixture(scope="function", autouse=True)
def reset_db():
    """Reset the database between tests"""
    yield
    import requests

    requests.post("http://localhost:5010/reset")
