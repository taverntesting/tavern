from unittest.mock import Mock

import pytest

from tavern.util.strict_util import StrictLevel


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
        "strict": StrictLevel.all_on(),
        "tavern_internal": {"pytest_hook_caller": Mock()},
    }

    return includes.copy()


@pytest.fixture(autouse=True)
def fix_hack_extensions(includes):
    class FakeFinder:
        @classmethod
        def find_distributions(cls, *args, **kwargs):

            class Wr:
                entry_points=[]

            return [Wr]

    import sys
    sys.meta_path.append(FakeFinder())
