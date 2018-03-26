import pytest


@pytest.fixture(name="includes")
def fix_example_includes():
    includes = {
        "variables": {
            "request_url": "www.google.com",
            "test_auth_token": "abc123",
            "code": "def456",
            "callback_url": "www.yahoo.co.uk",
        }
    }

    return includes.copy()
