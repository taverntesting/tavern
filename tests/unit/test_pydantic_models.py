"""Tests for pydantic-based key validation models."""

import pytest

from tavern._core import exceptions
from tavern._core.pydantic_models import (
    GRPCClientTopLevel,
    GRPCConnectArgs,
    GRPCProtoArgs,
    GRPCRequestSpec,
    GRPCResponseSpec,
    MQTTAuthArgs,
    MQTTClientArgs,
    MQTTClientTopLevel,
    MQTTConnectArgs,
    MQTTRequestSpec,
    MQTTSSLContextArgs,
    MQTTTLSArgs,
    RestRequestSpec,
)


class TestRestRequestSpec:
    def test_valid_keys(self):
        data = {"method": "GET", "url": "http://example.com", "json": {"a": 1}}
        result = RestRequestSpec.validate_keys(data)
        assert "method" in result
        assert "url" in result
        assert "json" in result

    def test_unexpected_key(self):
        data = {"method": "GET", "url": "http://example.com", "bad_key": "value"}
        with pytest.raises(exceptions.UnexpectedKeysError):
            RestRequestSpec.validate_keys(data)

    def test_empty_dict(self):
        result = RestRequestSpec.validate_keys({})
        assert result == {}


class TestMQTTRequestSpec:
    def test_valid_keys(self):
        data = {"topic": "test/topic", "payload": "hello", "qos": 1}
        result = MQTTRequestSpec.validate_keys(data)
        assert "topic" in result

    def test_unexpected_key(self):
        data = {"topic": "test/topic", "bad_key": "value"}
        with pytest.raises(exceptions.UnexpectedKeysError):
            MQTTRequestSpec.validate_keys(data)


class TestMQTTClientSpecs:
    def test_top_level_valid(self):
        data = {"client": {}, "connect": {"host": "localhost"}, "auth": {}}
        result = MQTTClientTopLevel.validate_keys(data)
        assert "client" in result

    def test_top_level_unexpected(self):
        data = {"client": {}, "bad_block": {}}
        with pytest.raises(exceptions.UnexpectedKeysError):
            MQTTClientTopLevel.validate_keys(data)

    def test_connect_args_valid(self):
        data = {"host": "localhost", "port": 1883, "keepalive": 60}
        result = MQTTConnectArgs.validate_keys(data)
        assert "host" in result

    def test_connect_args_unexpected(self):
        data = {"host": "localhost", "bad_key": "value"}
        with pytest.raises(exceptions.UnexpectedKeysError):
            MQTTConnectArgs.validate_keys(data)

    def test_client_args_valid(self):
        data = {"client_id": "test_id", "transport": "tcp"}
        result = MQTTClientArgs.validate_keys(data)
        assert "client_id" in result

    def test_client_args_unexpected(self):
        data = {"client_id": "test_id", "bad_key": "value"}
        with pytest.raises(exceptions.UnexpectedKeysError):
            MQTTClientArgs.validate_keys(data)

    def test_auth_args_valid(self):
        data = {"username": "user", "password": "pass"}
        result = MQTTAuthArgs.validate_keys(data)
        assert "username" in result

    def test_auth_args_unexpected(self):
        data = {"username": "user", "bad_key": "value"}
        with pytest.raises(exceptions.UnexpectedKeysError):
            MQTTAuthArgs.validate_keys(data)

    def test_tls_args_valid(self):
        data = {"enable": True, "ca_certs": "/path/to/ca"}
        result = MQTTTLSArgs.validate_keys(data)
        assert "enable" in result

    def test_tls_args_unexpected(self):
        data = {"enable": True, "bad_key": "value"}
        with pytest.raises(exceptions.UnexpectedKeysError):
            MQTTTLSArgs.validate_keys(data)

    def test_ssl_context_args_valid(self):
        data = {"ca_certs": "/path/to/ca", "alpn_protocols": ["h2"]}
        result = MQTTSSLContextArgs.validate_keys(data)
        assert "ca_certs" in result

    def test_ssl_context_args_unexpected(self):
        data = {"ca_certs": "/path/to/ca", "bad_key": "value"}
        with pytest.raises(exceptions.UnexpectedKeysError):
            MQTTSSLContextArgs.validate_keys(data)


class TestGRPCSpecs:
    def test_request_spec_valid(self):
        data = {"host": "localhost:50051", "service": "MyService/Method", "body": {}}
        result = GRPCRequestSpec.validate_keys(data)
        assert "host" in result

    def test_request_spec_unexpected(self):
        data = {"host": "localhost:50051", "bad_key": "value"}
        with pytest.raises(exceptions.UnexpectedKeysError):
            GRPCRequestSpec.validate_keys(data)

    def test_response_spec_valid(self):
        data = {"body": {}, "status": 0, "details": "ok", "save": {}}
        result = GRPCResponseSpec.validate_keys(data)
        assert "body" in result

    def test_response_spec_unexpected(self):
        data = {"body": {}, "bad_key": "value"}
        with pytest.raises(exceptions.UnexpectedKeysError):
            GRPCResponseSpec.validate_keys(data)

    def test_client_top_level_valid(self):
        data = {"connect": {"host": "localhost"}, "proto": {"source": "test.proto"}}
        result = GRPCClientTopLevel.validate_keys(data)
        assert "connect" in result

    def test_client_top_level_unexpected(self):
        data = {"connect": {}, "bad_block": {}}
        with pytest.raises(exceptions.UnexpectedKeysError):
            GRPCClientTopLevel.validate_keys(data)

    def test_connect_args_valid(self):
        data = {"host": "localhost", "port": 50051, "timeout": 5, "secure": False}
        result = GRPCConnectArgs.validate_keys(data)
        assert "host" in result

    def test_connect_args_unexpected(self):
        data = {"host": "localhost", "bad_key": "value"}
        with pytest.raises(exceptions.UnexpectedKeysError):
            GRPCConnectArgs.validate_keys(data)

    def test_proto_args_valid(self):
        data = {"source": "test.proto"}
        result = GRPCProtoArgs.validate_keys(data)
        assert "source" in result

    def test_proto_args_unexpected(self):
        data = {"source": "test.proto", "bad_key": "value"}
        with pytest.raises(exceptions.UnexpectedKeysError):
            GRPCProtoArgs.validate_keys(data)
