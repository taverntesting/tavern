import pytest


@pytest.fixture(name="includes")
def fix_example_includes():
    includes = {
        "variables": {
            "request": {
                "prefix": "www.",
                "url": "google.com",
            },
            "test_auth_token": "abc123",
            "code": "def456",
            "callback_url": "www.yahoo.co.uk",
            "request_topic": "/abc"
        },
        "backends": {
            "mqtt": "paho-mqtt",
            "http": "requests",
        }
    }

    return includes.copy()
