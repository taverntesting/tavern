"""Pydantic models for validating request/client specs.

Replaces the older ``check_expected_keys`` pattern with pydantic models
that use ``extra="forbid"`` to reject unexpected keys, providing the same
validation with better error messages and type safety.
"""

from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from tavern._core import exceptions


class _BaseKeyValidator(BaseModel):
    """Base model that forbids extra keys and raises UnexpectedKeysError on validation failure."""

    model_config = ConfigDict(
        extra="forbid", arbitrary_types_allowed=True, populate_by_name=True
    )

    @classmethod
    def validate_keys(cls, data: dict) -> dict:
        """Validate that ``data`` contains only expected keys.

        Args:
            data: Dictionary to validate against this model's fields.

        Returns:
            The validated data as a dict.

        Raises:
            exceptions.UnexpectedKeysError: If unexpected keys are present.
        """
        try:
            return cls(**data).model_dump(exclude_unset=True, by_alias=True)
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
    method: Optional[Any] = None
    url: Optional[Any] = None
    headers: Optional[Any] = None
    data: Optional[Any] = None
    params: Optional[Any] = None
    auth: Optional[Any] = None
    json_body: Optional[Any] = Field(default=None, alias="json")
    verify: Optional[Any] = None
    files: Optional[Any] = None
    file_body: Optional[Any] = None
    stream: Optional[Any] = None
    timeout: Optional[Any] = None
    cookies: Optional[Any] = None
    cert: Optional[Any] = None
    follow_redirects: Optional[Any] = None


# --- MQTT request spec ---
class MQTTRequestSpec(_BaseKeyValidator):
    topic: Optional[Any] = None
    payload: Optional[Any] = None
    json_body: Optional[Any] = Field(default=None, alias="json")
    qos: Optional[Any] = None
    retain: Optional[Any] = None


# --- MQTT client config blocks ---
class MQTTClientArgs(_BaseKeyValidator):
    client_id: Optional[Any] = None
    clean_session: Optional[Any] = None
    transport: Optional[Any] = None


class MQTTConnectArgs(_BaseKeyValidator):
    host: Optional[Any] = None
    port: Optional[Any] = None
    keepalive: Optional[Any] = None
    timeout: Optional[Any] = None


class MQTTAuthArgs(_BaseKeyValidator):
    username: Optional[Any] = None
    password: Optional[Any] = None


class MQTTTLSArgs(_BaseKeyValidator):
    enable: Optional[Any] = None
    ca_certs: Optional[Any] = None
    cert_reqs: Optional[Any] = None
    certfile: Optional[Any] = None
    keyfile: Optional[Any] = None
    tls_version: Optional[Any] = None
    ciphers: Optional[Any] = None


class MQTTSSLContextArgs(_BaseKeyValidator):
    ca_certs: Optional[Any] = None
    certfile: Optional[Any] = None
    keyfile: Optional[Any] = None
    password: Optional[Any] = None
    tls_version: Optional[Any] = None
    ciphers: Optional[Any] = None
    alpn_protocols: Optional[Any] = None


class MQTTClientTopLevel(_BaseKeyValidator):
    client: Optional[Any] = None
    connect: Optional[Any] = None
    tls: Optional[Any] = None
    auth: Optional[Any] = None
    ssl_context: Optional[Any] = None


# --- gRPC request spec ---
class GRPCRequestSpec(_BaseKeyValidator):
    host: Optional[Any] = None
    service: Optional[Any] = None
    body: Optional[Any] = None


# --- gRPC response spec ---
class GRPCResponseSpec(_BaseKeyValidator):
    body: Optional[Any] = None
    status: Optional[Any] = None
    details: Optional[Any] = None
    save: Optional[Any] = None


# --- gRPC client config blocks ---
class GRPCConnectArgs(_BaseKeyValidator):
    host: Optional[Any] = None
    port: Optional[Any] = None
    options: Optional[Any] = None
    timeout: Optional[Any] = None
    secure: Optional[Any] = None


class GRPCProtoArgs(_BaseKeyValidator):
    source: Optional[Any] = None
    module: Optional[Any] = None


class GRPCClientTopLevel(_BaseKeyValidator):
    connect: Optional[Any] = None
    proto: Optional[Any] = None
    metadata: Optional[Any] = None
    attempt_reflection: Optional[Any] = None
