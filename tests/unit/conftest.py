from mock import Mock
import pytest


@pytest.fixture(name="includes")
def fix_example_includes():
    includes = {
        "variables": {
            "request": {"prefix": "www.", "url": "google.com"},
            "test_auth_token": "abc123",
            "code": "def456",
            "callback_url": "www.yahoo.co.uk",
            "request_topic": "/abc",
        },
        "backends": {"mqtt": "paho-mqtt", "http": "requests"},
        "strict": True,
        "stages": [{
            "id": "my_external_stage",
            "name": "My external stage",
            "request": {
                "url": "http://www.bing.com",
                "method": "GET",
            },
            "response": {
                "status_code": 200,
                "body": {
                    "key": "value",
                },
                "headers": {
                    "content-type": "application/json",
                }
            }
        }],
        "tavern_internal": {
            "pytest_hook_caller": Mock(),
        }
    }

    return includes.copy()
