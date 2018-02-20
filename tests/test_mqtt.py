import pytest
from mock import patch

from tavern.mqtt import MQTTClient
from tavern.util import exceptions


class TestClient(object):
    
    def test_host_required(self):
        """Always needs a host, but it's the only required key"""
        with pytest.raises(exceptions.MissingKeysError):
            MQTTClient()

        args = {
            "connect": {
                "host": "localhost",
            }
        }

        MQTTClient(**args)
