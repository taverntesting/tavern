"""Pydantic models for validating request/client specs.

Replaces the older ``check_expected_keys`` pattern with pydantic models
that use ``extra="forbid"`` to reject unexpected keys, providing the same
validation with better error messages and type safety.
"""

from collections.abc import Mapping
from typing import Optional, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from tavern._core import exceptions

# Type alias for JSON-compatible values (any valid JSON type)
JSONType = Union[dict, list, str, int, float, bool, None]


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
    method: Optional[str] = None
    url: Optional[str] = None
    headers: Optional[dict] = None
    data: Optional[Union[dict, list, str, bytes]] = None
    params: Optional[dict] = None
    auth: Optional[Union[list, str]] = None
    json_body: Optional[JSONType] = Field(default=None, alias="json")
    verify: Optional[Union[bool, str]] = None
    files: Optional[Union[dict, list]] = None
    file_body: Optional[str] = None
    stream: Optional[bool] = None
    timeout: Optional[Union[float, list]] = None
    cookies: Optional[dict] = None
    cert: Optional[Union[str, list]] = None
    follow_redirects: Optional[bool] = None


# --- MQTT request spec ---
class MQTTRequestSpec(_BaseKeyValidator):
    topic: Optional[str] = None
    payload: Optional[Union[str, bytes, int, float]] = None
    json_body: Optional[JSONType] = Field(default=None, alias="json")
    qos: Optional[int] = None
    retain: Optional[bool] = None


# --- MQTT client config blocks ---
class MQTTClientArgs(_BaseKeyValidator):
    client_id: Optional[str] = None
    clean_session: Optional[bool] = None
    transport: Optional[str] = None


class MQTTConnectArgs(_BaseKeyValidator):
    host: Optional[str] = None
    port: Optional[int] = None
    keepalive: Optional[int] = None
    timeout: Optional[Union[int, float]] = None


class MQTTAuthArgs(_BaseKeyValidator):
    username: Optional[str] = None
    password: Optional[str] = None


class MQTTTLSArgs(_BaseKeyValidator):
    enable: Optional[bool] = None
    ca_certs: Optional[str] = None
    cert_reqs: Optional[str] = None
    certfile: Optional[str] = None
    keyfile: Optional[str] = None
    tls_version: Optional[str] = None
    ciphers: Optional[str] = None


class MQTTSSLContextArgs(_BaseKeyValidator):
    ca_certs: Optional[str] = None
    certfile: Optional[str] = None
    keyfile: Optional[str] = None
    password: Optional[str] = None
    tls_version: Optional[str] = None
    ciphers: Optional[str] = None
    alpn_protocols: Optional[list[str]] = None


class MQTTClientTopLevel(_BaseKeyValidator):
    client: Optional[dict] = None
    connect: Optional[dict] = None
    tls: Optional[dict] = None
    auth: Optional[dict] = None
    ssl_context: Optional[dict] = None


# --- gRPC request spec ---
class GRPCRequestSpec(_BaseKeyValidator):
    host: Optional[str] = None
    service: Optional[str] = None
    body: Optional[Union[dict, str]] = None


# --- gRPC response spec ---
class GRPCResponseSpec(_BaseKeyValidator):
    body: Optional[dict] = None
    status: Optional[Union[str, int, list[str], list[int]]] = None
    details: Optional[str] = None
    save: Optional[dict] = None


# --- gRPC client config blocks ---
class GRPCConnectArgs(_BaseKeyValidator):
    host: Optional[str] = None
    port: Optional[int] = None
    options: Optional[dict] = None
    timeout: Optional[int] = None
    secure: Optional[bool] = None


class GRPCProtoArgs(_BaseKeyValidator):
    source: Optional[str] = None
    module: Optional[str] = None


class GRPCClientTopLevel(_BaseKeyValidator):
    connect: Optional[dict] = None
    proto: Optional[dict] = None
    metadata: Optional[dict] = None
    attempt_reflection: Optional[bool] = None
