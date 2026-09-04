"""Pydantic models for validating request/client specs.

Replaces the older ``check_expected_keys`` pattern with pydantic models
that use ``extra="forbid"`` to reject unexpected keys, providing the same
validation with better error messages and type safety.
"""

from collections.abc import Mapping
from typing import Optional, Union

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from tavern._core import exceptions
from tavern._core.loader import (
    BoolToken,
    FloatToken,
    ForceIncludeToken,
    IntToken,
)

# Type alias for JSON-compatible values (any valid JSON type), plus
# conversion tokens for pre-resolution YAML tags like !force_format_include
# and !int/!float/!bool, and dict for pre-resolution $ext function calls.
JSONType = Union[
    dict,
    list,
    str,
    int,
    float,
    bool,
    None,
    IntToken,
    FloatToken,
    BoolToken,
    ForceIncludeToken,
]


class _BaseKeyValidator(BaseModel):
    """Base model that forbids extra keys and raises UnexpectedKeysError on validation failure."""

    model_config = ConfigDict(
        extra="forbid",
        arbitrary_types_allowed=True,
        populate_by_name=True,
        hide_input_in_errors=True,
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
            missing = set()
            for err in e.errors():
                if err["type"] == "extra_forbidden":
                    unexpected.add(err["loc"][-1])
                elif err["type"] == "missing":
                    missing.add(err["loc"][-1])
            if unexpected:
                msg = f"Unexpected keys {unexpected}"
                raise exceptions.UnexpectedKeysError(msg) from e
            elif missing:
                msg = f"Missing keys {missing}"
                raise exceptions.MissingKeysError(msg) from e
            else:
                msg = str(e)
                raise exceptions.UnexpectedKeysError(msg) from e


# --- REST request spec ---
class RestRequestSpec(_BaseKeyValidator):
    method: Optional[str] = None
    url: Union[str, dict]  # required; dict for pre-resolution $ext
    headers: Optional[dict] = None  # dict for pre-resolution $ext
    data: Optional[Union[dict, list, str, bytes, int, float]] = None
    params: Optional[dict] = None  # dict for pre-resolution $ext
    auth: Optional[Union[list, str, dict]] = None  # dict for pre-resolution $ext
    json_body: Optional[JSONType] = Field(default=None, alias="json")
    verify: Optional[Union[bool, str]] = None
    files: Optional[Union[dict, list]] = None  # dict for pre-resolution $ext
    file_body: Optional[str] = None
    stream: Optional[bool] = None
    timeout: Optional[Union[float, int, list, str, dict]] = None  # dict for $ext
    cookies: Optional[Union[dict, list]] = None
    cert: Optional[Union[str, list, int, dict]] = None  # dict for $ext
    follow_redirects: Optional[bool] = None


# --- MQTT request spec ---
class MQTTRequestSpec(_BaseKeyValidator):
    topic: Optional[str] = None
    payload: Optional[Union[str, bytes, int, float]] = None
    json_body: Optional[JSONType] = Field(default=None, alias="json")
    qos: Optional[Union[int, IntToken]] = None
    retain: Optional[Union[bool, BoolToken]] = None


# --- MQTT client config blocks ---
class MQTTClientArgs(_BaseKeyValidator):
    client_id: Optional[str] = None
    clean_session: Optional[Union[bool, BoolToken]] = None
    transport: Optional[str] = None


class MQTTConnectArgs(_BaseKeyValidator):
    host: str  # required
    port: Optional[Union[int, IntToken]] = None
    keepalive: Optional[Union[int, IntToken]] = None
    timeout: Optional[Union[int, float, IntToken, FloatToken]] = None


class MQTTAuthArgs(_BaseKeyValidator):
    username: str  # required
    password: Optional[str] = None


class MQTTTLSArgs(_BaseKeyValidator):
    enable: Optional[Union[bool, BoolToken]] = None
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
    service: str  # required
    body: Optional[Union[dict, str]] = None


# --- gRPC response spec ---
class GRPCResponseSpec(_BaseKeyValidator):
    body: Optional[dict] = None
    status: Optional[Union[str, int, list[str], list[int]]] = None
    details: Optional[Union[str, dict]] = None
    save: Optional[dict] = None


# --- gRPC client config blocks ---
class GRPCConnectArgs(_BaseKeyValidator):
    host: Optional[str] = None
    port: Optional[Union[int, IntToken]] = None
    options: Optional[dict] = None
    timeout: Optional[Union[int, IntToken]] = None
    secure: Optional[Union[bool, BoolToken]] = None


class GRPCProtoArgs(_BaseKeyValidator):
    source: Optional[str] = None
    module: Optional[str] = None


class GRPCClientTopLevel(_BaseKeyValidator):
    connect: Optional[dict] = None
    proto: Optional[dict] = None
    metadata: Optional[dict] = None
    attempt_reflection: Optional[Union[bool, BoolToken]] = None
