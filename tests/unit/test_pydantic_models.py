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
        """url is required, so an empty dict should fail"""
        with pytest.raises(exceptions.MissingKeysError):
            RestRequestSpec.validate_keys({})


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


class TestTypeValidation:
    """Tests verifying that pydantic models enforce type checking, not just key validation."""

    def test_rest_method_must_be_string(self):
        data = {"url": "http://example.com", "method": 123}
        with pytest.raises(exceptions.UnexpectedKeysError):
            RestRequestSpec.validate_keys(data)

    def test_rest_stream_must_be_bool(self):
        data = {"url": "http://example.com", "stream": "not_a_bool"}
        with pytest.raises(exceptions.UnexpectedKeysError):
            RestRequestSpec.validate_keys(data)

    def test_rest_verify_can_be_bool(self):
        data = {"url": "http://example.com", "verify": False}
        result = RestRequestSpec.validate_keys(data)
        assert result["verify"] is False

    def test_rest_verify_can_be_string(self):
        data = {"url": "http://example.com", "verify": "/path/to/ca.pem"}
        result = RestRequestSpec.validate_keys(data)
        assert result["verify"] == "/path/to/ca.pem"

    def test_rest_json_can_be_dict(self):
        data = {"url": "http://example.com", "json": {"key": "value"}}
        result = RestRequestSpec.validate_keys(data)
        assert result["json"] == {"key": "value"}

    def test_rest_json_can_be_list(self):
        data = {"url": "http://example.com", "json": [1, 2, 3]}
        result = RestRequestSpec.validate_keys(data)
        assert result["json"] == [1, 2, 3]

    def test_rest_json_can_be_string(self):
        data = {"url": "http://example.com", "json": "hello"}
        result = RestRequestSpec.validate_keys(data)
        assert result["json"] == "hello"

    def test_rest_json_can_be_int(self):
        data = {"url": "http://example.com", "json": 42}
        result = RestRequestSpec.validate_keys(data)
        assert result["json"] == 42

    def test_rest_json_can_be_bool(self):
        data = {"url": "http://example.com", "json": True}
        result = RestRequestSpec.validate_keys(data)
        assert result["json"] is True

    def test_rest_headers_must_be_dict(self):
        data = {"url": "http://example.com", "headers": "not_a_dict"}
        with pytest.raises(exceptions.UnexpectedKeysError):
            RestRequestSpec.validate_keys(data)

    def test_rest_timeout_can_be_float(self):
        data = {"url": "http://example.com", "timeout": 30.0}
        result = RestRequestSpec.validate_keys(data)
        assert result["timeout"] == 30.0

    def test_rest_timeout_can_be_list(self):
        data = {"url": "http://example.com", "timeout": [5.0, 30.0]}
        result = RestRequestSpec.validate_keys(data)
        assert result["timeout"] == [5.0, 30.0]

    def test_mqtt_topic_must_be_string(self):
        data = {"topic": 123}
        with pytest.raises(exceptions.UnexpectedKeysError):
            MQTTRequestSpec.validate_keys(data)

    def test_mqtt_qos_must_be_int(self):
        data = {"topic": "test/topic", "qos": "not_an_int"}
        with pytest.raises(exceptions.UnexpectedKeysError):
            MQTTRequestSpec.validate_keys(data)

    def test_mqtt_qos_accepts_int(self):
        data = {"topic": "test/topic", "qos": 1}
        result = MQTTRequestSpec.validate_keys(data)
        assert result["qos"] == 1

    def test_mqtt_retain_must_be_bool(self):
        data = {"topic": "test/topic", "retain": "not_a_bool"}
        with pytest.raises(exceptions.UnexpectedKeysError):
            MQTTRequestSpec.validate_keys(data)

    def test_mqtt_retain_accepts_bool(self):
        data = {"topic": "test/topic", "retain": True}
        result = MQTTRequestSpec.validate_keys(data)
        assert result["retain"] is True

    def test_mqtt_connect_host_must_be_string(self):
        data = {"host": 123}
        with pytest.raises(exceptions.UnexpectedKeysError):
            MQTTConnectArgs.validate_keys(data)

    def test_mqtt_connect_port_must_be_int(self):
        data = {"host": "localhost", "port": "not_an_int"}
        with pytest.raises(exceptions.UnexpectedKeysError):
            MQTTConnectArgs.validate_keys(data)

    def test_mqtt_connect_port_accepts_int(self):
        data = {"host": "localhost", "port": 1883}
        result = MQTTConnectArgs.validate_keys(data)
        assert result["port"] == 1883

    def test_mqtt_tls_enable_must_be_bool(self):
        data = {"enable": "not_a_bool"}
        with pytest.raises(exceptions.UnexpectedKeysError):
            MQTTTLSArgs.validate_keys(data)

    def test_mqtt_tls_enable_accepts_bool(self):
        data = {"enable": True}
        result = MQTTTLSArgs.validate_keys(data)
        assert result["enable"] is True

    def test_mqtt_tls_enable_rejects_dict(self):
        data = {"enable": {"$ext": {"function": "some_func"}}}
        with pytest.raises(exceptions.UnexpectedKeysError):
            MQTTTLSArgs.validate_keys(data)

    def test_mqtt_ssl_alpn_protocols_must_be_list(self):
        data = {"alpn_protocols": "h2"}
        with pytest.raises(exceptions.UnexpectedKeysError):
            MQTTSSLContextArgs.validate_keys(data)

    def test_mqtt_ssl_alpn_protocols_accepts_list(self):
        data = {"alpn_protocols": ["h2", "http/1.1"]}
        result = MQTTSSLContextArgs.validate_keys(data)
        assert result["alpn_protocols"] == ["h2", "http/1.1"]

    def test_mqtt_client_top_level_blocks_must_be_dict(self):
        data = {"client": "not_a_dict"}
        with pytest.raises(exceptions.UnexpectedKeysError):
            MQTTClientTopLevel.validate_keys(data)

    def test_grpc_request_host_must_be_string(self):
        data = {"service": "MyService/Method", "host": 123}
        with pytest.raises(exceptions.UnexpectedKeysError):
            GRPCRequestSpec.validate_keys(data)

    def test_grpc_request_body_can_be_dict(self):
        data = {
            "host": "localhost:50051",
            "service": "MyService/Method",
            "body": {"key": "value"},
        }
        result = GRPCRequestSpec.validate_keys(data)
        assert result["body"] == {"key": "value"}

    def test_grpc_request_body_can_be_string(self):
        data = {
            "host": "localhost:50051",
            "service": "MyService/Method",
            "body": "raw string",
        }
        result = GRPCRequestSpec.validate_keys(data)
        assert result["body"] == "raw string"

    def test_grpc_response_status_can_be_int(self):
        data = {"status": 0}
        result = GRPCResponseSpec.validate_keys(data)
        assert result["status"] == 0

    def test_grpc_response_status_can_be_string(self):
        data = {"status": "OK"}
        result = GRPCResponseSpec.validate_keys(data)
        assert result["status"] == "OK"

    def test_grpc_response_status_can_be_list_of_strings(self):
        data = {"status": ["OK", "CANCELLED"]}
        result = GRPCResponseSpec.validate_keys(data)
        assert result["status"] == ["OK", "CANCELLED"]

    def test_grpc_response_status_can_be_list_of_ints(self):
        data = {"status": [0, 1]}
        result = GRPCResponseSpec.validate_keys(data)
        assert result["status"] == [0, 1]

    def test_grpc_connect_port_must_be_int(self):
        data = {"host": "localhost", "port": "not_an_int"}
        with pytest.raises(exceptions.UnexpectedKeysError):
            GRPCConnectArgs.validate_keys(data)

    def test_grpc_connect_secure_must_be_bool(self):
        data = {"host": "localhost", "secure": "not_a_bool"}
        with pytest.raises(exceptions.UnexpectedKeysError):
            GRPCConnectArgs.validate_keys(data)

    def test_grpc_connect_secure_accepts_bool(self):
        data = {"host": "localhost", "secure": True}
        result = GRPCConnectArgs.validate_keys(data)
        assert result["secure"] is True

    def test_grpc_client_attempt_reflection_must_be_bool(self):
        data = {"attempt_reflection": "not_a_bool"}
        with pytest.raises(exceptions.UnexpectedKeysError):
            GRPCClientTopLevel.validate_keys(data)

    def test_grpc_client_attempt_reflection_accepts_bool(self):
        data = {"attempt_reflection": True}
        result = GRPCClientTopLevel.validate_keys(data)
        assert result["attempt_reflection"] is True


class TestRequiredFields:
    """Tests verifying that required fields are enforced."""

    def test_rest_url_is_required(self):
        data = {"method": "GET"}
        with pytest.raises(exceptions.MissingKeysError):
            RestRequestSpec.validate_keys(data)

    def test_mqtt_connect_host_is_required(self):
        data = {"port": 1883}
        with pytest.raises(exceptions.MissingKeysError):
            MQTTConnectArgs.validate_keys(data)

    def test_mqtt_auth_username_is_required(self):
        data = {"password": "pass"}
        with pytest.raises(exceptions.MissingKeysError):
            MQTTAuthArgs.validate_keys(data)

    def test_grpc_request_service_is_required(self):
        data = {"host": "localhost:50051"}
        with pytest.raises(exceptions.MissingKeysError):
            GRPCRequestSpec.validate_keys(data)


class TestSpecificTokenTypes:
    """Tests verifying that conversion tokens are type-specific."""

    def test_mqtt_qos_accepts_int_token(self):
        from tavern._core.loader import IntToken

        data = {"topic": "test/topic", "qos": IntToken("{qos:d}")}
        result = MQTTRequestSpec.validate_keys(data)
        assert "qos" in result

    def test_mqtt_qos_rejects_bool_token(self):
        from tavern._core.loader import BoolToken

        data = {"topic": "test/topic", "qos": BoolToken("{qos:d}")}
        with pytest.raises(exceptions.UnexpectedKeysError):
            MQTTRequestSpec.validate_keys(data)

    def test_mqtt_retain_accepts_bool_token(self):
        from tavern._core.loader import BoolToken

        data = {"topic": "test/topic", "retain": BoolToken("{retain:d}")}
        result = MQTTRequestSpec.validate_keys(data)
        assert "retain" in result

    def test_mqtt_retain_rejects_int_token(self):
        from tavern._core.loader import IntToken

        data = {"topic": "test/topic", "retain": IntToken("{retain:d}")}
        with pytest.raises(exceptions.UnexpectedKeysError):
            MQTTRequestSpec.validate_keys(data)

    def test_mqtt_connect_port_accepts_int_token(self):
        from tavern._core.loader import IntToken

        data = {"host": "localhost", "port": IntToken("{port:d}")}
        result = MQTTConnectArgs.validate_keys(data)
        assert "port" in result

    def test_grpc_connect_port_rejects_bool_token(self):
        from tavern._core.loader import BoolToken

        data = {"host": "localhost", "port": BoolToken("{port:d}")}
        with pytest.raises(exceptions.UnexpectedKeysError):
            GRPCConnectArgs.validate_keys(data)

    def test_rest_method_rejects_dict(self):
        data = {
            "url": "http://example.com",
            "method": {"$ext": {"function": "mod:func"}},
        }
        with pytest.raises(exceptions.UnexpectedKeysError):
            RestRequestSpec.validate_keys(data)

    def test_rest_verify_rejects_dict(self):
        data = {
            "url": "http://example.com",
            "verify": {"$ext": {"function": "mod:func"}},
        }
        with pytest.raises(exceptions.UnexpectedKeysError):
            RestRequestSpec.validate_keys(data)

    def test_mqtt_topic_rejects_dict(self):
        data = {"topic": {"$ext": {"function": "mod:func"}}}
        with pytest.raises(exceptions.UnexpectedKeysError):
            MQTTRequestSpec.validate_keys(data)

    def test_mqtt_payload_rejects_dict(self):
        data = {"topic": "test/topic", "payload": {"key": "value"}}
        with pytest.raises(exceptions.UnexpectedKeysError):
            MQTTRequestSpec.validate_keys(data)

    def test_grpc_response_status_rejects_dict(self):
        data = {"status": {"key": "value"}}
        with pytest.raises(exceptions.UnexpectedKeysError):
            GRPCResponseSpec.validate_keys(data)
