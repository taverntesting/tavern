"""Pydantic models for validating request/client specs.

Replaces the older ``check_expected_keys`` pattern with pydantic models
that use ``extra="forbid"`` to reject unexpected keys, providing the same
validation with better error messages and type safety.
"""

import warnings
from collections.abc import Mapping
from typing import Optional, Union, get_args

from pydantic import (
    BaseModel,
    ConfigDict,
    InstanceOf,
    ValidationError,
    ValidationInfo,
    field_validator,
)

from tavern._core import exceptions
from tavern._core.loader import (
    AnythingSentinel,
    BoolToken,
    FloatToken,
    ForceIncludeToken,
    IntToken,
    ListSentinel,
    RawStrToken,
    RegexSentinel,
    StrSentinel,
    TypeSentinel,
)

# Type alias for JSON-compatible values (any valid JSON type), plus
# the pre-resolution !force_format_include token, and dict for
# pre-resolution $ext function calls.
JSONType = Union[
    dict,
    list,
    str,
    int,
    float,
    bool,
    None,
    ForceIncludeToken,
]

# A field annotated with one of these types also accepts the matching
# !bool/!int/!float/!raw token, which is converted after formatting.
_TOKEN_TARGETS: dict[type, type] = {
    BoolToken: bool,
    IntToken: int,
    FloatToken: float,
    RawStrToken: str,
}

# 'json' fields shadow the deprecated BaseModel.json(); only model_dump() is used.
# The 'json' method is deprecated anyway
warnings.filterwarnings(
    "ignore",
    message=r'Field name "json" in ".*" shadows an attribute',
    category=UserWarning,
)


class _BaseKeyValidator(BaseModel):
    """Base model that forbids extra keys and raises UnexpectedKeysError on validation failure."""

    model_config = ConfigDict(
        extra="forbid",
        arbitrary_types_allowed=True,
        hide_input_in_errors=True,
    )

    @field_validator("*", mode="wrap")
    @classmethod
    def _accept_conversion_tokens(cls, value, handler, info: ValidationInfo):
        target = _TOKEN_TARGETS.get(type(value))
        annotation = cls.model_fields[info.field_name].annotation  # type:ignore[index]
        if target is not None and (
            annotation is target or target in get_args(annotation)
        ):
            return value
        return handler(value)

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
            # warnings=False: token values do not match their field's serializer
            return cls(**dict(data)).model_dump(exclude_unset=True, warnings=False)
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
    json: Optional[JSONType] = None
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
    json: Optional[JSONType] = None
    qos: Optional[int] = None
    retain: Optional[bool] = None


# --- MQTT response spec ---
class MQTTResponseItemSpec(_BaseKeyValidator):
    topic: str  # required
    unexpected: Optional[bool] = None
    payload: Optional[Union[str, int, float, bool, TypeSentinel]] = None
    json: Optional[JSONType] = None
    timeout: Optional[Union[int, float]] = None
    qos: Optional[int] = None
    verify_response_with: Optional[Union[dict, list]] = None
    save: Optional[dict] = None


class MQTTResponseSpec(_BaseKeyValidator):
    mqtt_responses: list[MQTTResponseItemSpec]


# --- MQTT client config blocks ---
class MQTTClientArgs(_BaseKeyValidator):
    client_id: Optional[str] = None
    clean_session: Optional[bool] = None
    transport: Optional[str] = None


class MQTTConnectArgs(_BaseKeyValidator):
    host: str  # required
    port: Optional[int] = None
    keepalive: Optional[int] = None
    timeout: Optional[Union[int, float]] = None


class MQTTAuthArgs(_BaseKeyValidator):
    username: str  # required
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
    client: Optional[MQTTClientArgs] = None
    connect: Optional[MQTTConnectArgs] = None
    tls: Optional[MQTTTLSArgs] = None
    auth: Optional[MQTTAuthArgs] = None
    ssl_context: Optional[MQTTSSLContextArgs] = None


# --- gRPC request spec ---
class GRPCRequestSpec(_BaseKeyValidator):
    host: Optional[str] = None
    service: str  # required
    body: Optional[Union[dict, str]] = None


# --- gRPC response spec ---
class GRPCResponseSpec(_BaseKeyValidator):
    body: Optional[dict] = None
    status: Optional[Union[str, int, list[str], list[int]]] = None
    error_message: Optional[
        Union[str, StrSentinel, InstanceOf[RegexSentinel], AnythingSentinel]
    ] = None
    details: Optional[Union[list, str, ListSentinel, AnythingSentinel]] = None
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
    connect: Optional[GRPCConnectArgs] = None
    proto: Optional[GRPCProtoArgs] = None
    metadata: Optional[dict] = None
    attempt_reflection: Optional[bool] = None
