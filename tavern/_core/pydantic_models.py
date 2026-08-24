"""Pydantic models for validating request/client specs.

Replaces the older ``check_expected_keys`` pattern with pydantic models
that use ``extra="forbid"`` to reject unexpected keys, providing the same
validation with better error messages and type safety.
"""

from collections.abc import Mapping
from typing import Optional, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from tavern._core import exceptions
from tavern._core.loader import TypeConvertToken

# Type alias for JSON-compatible values (any valid JSON type), plus
# TypeConvertToken for pre-resolution YAML tags like !force_format_include
# and dict for pre-resolution $ext function calls.
JSONType = Union[dict, list, str, int, float, bool, None, TypeConvertToken]


class _BaseKeyValidator(BaseModel):
    """Base model that forbids extra keys and raises UnexpectedKeysError on validation failure."""

    model_config = ConfigDict(
        extra="forbid", arbitrary_types_allowed=True, populate_by_name=True
    )

    @classmethod
    def validate_keys(cls, data: Mapping) -> dict:
        """Validate that ``data`` contains only expected keys and types.

        Args:
            data: Dictionary to validate against this model's fields.

        Returns:
            The validated data as a dict.

        Raises:
            exceptions.UnexpectedKeysError: If unexpected keys are present or
                a value has an invalid type.
        """
        try:
            return cls(**dict(data)).model_dump(exclude_unset=True, by_alias=True)
        except ValidationError as e:
            # Extract unexpected field names from the error
            unexpected = set()
            for err in e.errors():
                if err["type"] == "extra_forbidden":
                    unexpected.add(err["loc"][-1])
            if unexpected:
                msg = f"Unexpected keys {unexpected}"
            else:
                msg = str(e)
            raise exceptions.UnexpectedKeysError(msg) from e


# --- REST request spec ---
class RestRequestSpec(_BaseKeyValidator):
    method: Optional[Union[str, dict, TypeConvertToken]] = None
    url: Optional[Union[str, dict, TypeConvertToken]] = None
    headers: Optional[Union[dict, TypeConvertToken]] = None
    data: Optional[Union[dict, list, str, bytes, int, float, TypeConvertToken]] = None
    params: Optional[Union[dict, TypeConvertToken]] = None
    auth: Optional[Union[list, str, dict, TypeConvertToken]] = None
    json_body: Optional[JSONType] = Field(default=None, alias="json")
    verify: Optional[Union[bool, str, dict, TypeConvertToken]] = None
    files: Optional[Union[dict, list, TypeConvertToken]] = None
    file_body: Optional[Union[str, dict, TypeConvertToken]] = None
    stream: Optional[Union[bool, TypeConvertToken]] = None
    timeout: Optional[Union[float, int, list, str, dict, TypeConvertToken]] = None
    cookies: Optional[Union[dict, list, TypeConvertToken]] = None
    cert: Optional[Union[str, list, int, dict, TypeConvertToken]] = None
    follow_redirects: Optional[Union[bool, TypeConvertToken]] = None


# --- MQTT request spec ---
class MQTTRequestSpec(_BaseKeyValidator):
    topic: Optional[Union[str, dict, TypeConvertToken]] = None
    payload: Optional[Union[str, bytes, int, float, dict, TypeConvertToken]] = None
    json_body: Optional[JSONType] = Field(default=None, alias="json")
    qos: Optional[Union[int, dict, TypeConvertToken]] = None
    retain: Optional[Union[bool, TypeConvertToken]] = None


# --- MQTT client config blocks ---
class MQTTClientArgs(_BaseKeyValidator):
    client_id: Optional[Union[str, dict, TypeConvertToken]] = None
    clean_session: Optional[Union[bool, TypeConvertToken]] = None
    transport: Optional[Union[str, dict, TypeConvertToken]] = None


class MQTTConnectArgs(_BaseKeyValidator):
    host: Optional[Union[str, dict, TypeConvertToken]] = None
    port: Optional[Union[int, dict, TypeConvertToken]] = None
    keepalive: Optional[Union[int, dict, TypeConvertToken]] = None
    timeout: Optional[Union[int, float, dict, TypeConvertToken]] = None


class MQTTAuthArgs(_BaseKeyValidator):
    username: Optional[Union[str, dict, TypeConvertToken]] = None
    password: Optional[Union[str, dict, TypeConvertToken]] = None


class MQTTTLSArgs(_BaseKeyValidator):
    enable: Optional[Union[bool, TypeConvertToken]] = None
    ca_certs: Optional[Union[str, dict, TypeConvertToken]] = None
    cert_reqs: Optional[Union[str, dict, TypeConvertToken]] = None
    certfile: Optional[Union[str, dict, TypeConvertToken]] = None
    keyfile: Optional[Union[str, dict, TypeConvertToken]] = None
    tls_version: Optional[Union[str, dict, TypeConvertToken]] = None
    ciphers: Optional[Union[str, dict, TypeConvertToken]] = None


class MQTTSSLContextArgs(_BaseKeyValidator):
    ca_certs: Optional[Union[str, dict, TypeConvertToken]] = None
    certfile: Optional[Union[str, dict, TypeConvertToken]] = None
    keyfile: Optional[Union[str, dict, TypeConvertToken]] = None
    password: Optional[Union[str, dict, TypeConvertToken]] = None
    tls_version: Optional[Union[str, dict, TypeConvertToken]] = None
    ciphers: Optional[Union[str, dict, TypeConvertToken]] = None
    alpn_protocols: Optional[Union[list[str], dict, TypeConvertToken]] = None


class MQTTClientTopLevel(_BaseKeyValidator):
    client: Optional[Union[dict, TypeConvertToken]] = None
    connect: Optional[Union[dict, TypeConvertToken]] = None
    tls: Optional[Union[dict, TypeConvertToken]] = None
    auth: Optional[Union[dict, TypeConvertToken]] = None
    ssl_context: Optional[Union[dict, TypeConvertToken]] = None


# --- gRPC request spec ---
class GRPCRequestSpec(_BaseKeyValidator):
    host: Optional[Union[str, dict, TypeConvertToken]] = None
    service: Optional[Union[str, dict, TypeConvertToken]] = None
    body: Optional[Union[dict, str, TypeConvertToken]] = None


# --- gRPC response spec ---
class GRPCResponseSpec(_BaseKeyValidator):
    body: Optional[Union[dict, TypeConvertToken]] = None
    status: Optional[Union[str, int, list[str], list[int], dict, TypeConvertToken]] = (
        None
    )
    details: Optional[Union[str, dict, TypeConvertToken]] = None
    save: Optional[Union[dict, TypeConvertToken]] = None


# --- gRPC client config blocks ---
class GRPCConnectArgs(_BaseKeyValidator):
    host: Optional[Union[str, dict, TypeConvertToken]] = None
    port: Optional[Union[int, dict, TypeConvertToken]] = None
    options: Optional[Union[dict, TypeConvertToken]] = None
    timeout: Optional[Union[int, dict, TypeConvertToken]] = None
    secure: Optional[Union[bool, TypeConvertToken]] = None


class GRPCProtoArgs(_BaseKeyValidator):
    source: Optional[Union[str, dict, TypeConvertToken]] = None
    module: Optional[Union[str, dict, TypeConvertToken]] = None


class GRPCClientTopLevel(_BaseKeyValidator):
    connect: Optional[Union[dict, TypeConvertToken]] = None
    proto: Optional[Union[dict, TypeConvertToken]] = None
    metadata: Optional[Union[dict, TypeConvertToken]] = None
    attempt_reflection: Optional[Union[bool, TypeConvertToken]] = None
