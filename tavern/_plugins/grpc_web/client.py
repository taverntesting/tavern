from __future__ import annotations

import dataclasses
import logging
from collections.abc import Mapping
from typing import Any
from urllib.parse import unquote, urljoin

import requests
from google.protobuf import json_format
from google.protobuf.json_format import ParseError
from google.protobuf.message import DecodeError
from google.protobuf.message_factory import GetMessageClass
from google.protobuf.symbol_database import Default
from tavern._core import exceptions
from tavern._core.dict_util import check_expected_keys
from tavern._plugins.grpc.protos import _generate_proto_import, _import_grpc_module
from tavern._plugins.grpc_web.codec import decode_grpc_web_body, encode_data_frame

logger = logging.getLogger(__name__)


def _split_service_method(full: str) -> tuple[str, str]:
    # gRPC-Web still targets canonical gRPC paths: package.Service/Method
    if "/" not in full:
        raise exceptions.GRPCRequestException(
            f"The service field must be in package.Service/Method format, got: {full!r}"
        )

    service, method = full.rsplit("/", 1)
    if not service or not method:
        raise exceptions.GRPCRequestException(
            f"Invalid service/method name: {full!r}"
        )

    return service, method


class GRPCWebSession:
    def __init__(self, **kwargs: Any) -> None:
        expected_blocks = {
            "connect": {
                "base_url",
                "path_prefix",
                "timeout",
                "verify",
                "headers",
            },
            "proto": {"source", "module"},
        }
        check_expected_keys(expected_blocks.keys(), kwargs)

        connect = kwargs.pop("connect", {}) or {}
        check_expected_keys(expected_blocks["connect"], connect)

        proto_args = kwargs.pop("proto", {}) or {}
        check_expected_keys(expected_blocks["proto"], proto_args)

        if kwargs:
            raise exceptions.BadSchemaError(
                f"Unexpected keys in grpc_web configuration: {set(kwargs)!r}"
            )

        self.base_url = (connect.get("base_url") or "").rstrip("/")
        if not self.base_url:
            raise exceptions.BadSchemaError(
                "Please provide grpc_web.connect.base_url"
            )

        path_prefix = connect.get("path_prefix")
        if path_prefix is None:
            path_prefix = "rpc"
        # Empty string is valid and means "mount RPC methods at root"
        self.path_prefix = str(path_prefix).strip("/")
        self.timeout = float(connect.get("timeout", 30))
        self.verify = connect.get("verify", True)
        raw_headers = dict(connect.get("headers") or {})
        self.default_headers: dict[str, str] = {
            k: str(v) for k, v in raw_headers.items() if str(v).strip() != ""
        }

        self.sym_db = Default()

        proto_source = proto_args.get("source")
        proto_module = proto_args.get("module")
        if not proto_source and not proto_module:
            raise exceptions.BadSchemaError(
                "In grpc_web.proto, provide at least one of: module or source"
            )

        if proto_source:
            _generate_proto_import(proto_source)

        if proto_module:
            try:
                _import_grpc_module(proto_module)
            except (ImportError, ModuleNotFoundError) as e:
                logger.exception("Failed to import protobuf module: %s", proto_module)
                raise exceptions.GRPCServiceException(
                    "Failed to import generated protobuf/grpc modules"
                ) from e

        self._session = requests.Session()
        # gRPC-Web requests are regular HTTP POST calls with these required headers
        self._session.headers.update(
            {
                "Content-Type": "application/grpc-web+proto",
                "X-Grpc-Web": "1",
            }
        )
        self._session.headers.update(self.default_headers)

    def get_method_types(self, service: str, method: str):
        pool = self.sym_db.pool
        grpc_service = pool.FindServiceByName(service)
        m = grpc_service.FindMethodByName(method)
        input_type = GetMessageClass(m.input_type)
        output_type = GetMessageClass(m.output_type)
        return input_type, output_type

    def call(
            self,
            *,
            service: str,
            body: Mapping | None,
            timeout: float | None = None,
            headers: Mapping[str, str] | None = None,
    ) -> "GRPCWebResult":
        svc, meth = _split_service_method(service)
        input_type, output_type = self.get_method_types(svc, meth)
        path = f"{self.path_prefix}/{svc}/{meth}"
        url = urljoin(self.base_url + "/", path)

        req = input_type()
        if body is not None:
            try:
                # ParseDict validates payload fields against the protobuf schema
                json_format.ParseDict(dict(body), req)
            except ParseError as e:
                raise exceptions.GRPCRequestException(
                    "Failed to build request from JSON payload (body/json)"
                ) from e

        payload = encode_data_frame(req.SerializeToString())
        merged_headers = {
            k: str(v)
            for k, v in (headers or {}).items()
            if str(v).strip() != ""
        }

        logger.debug(
            "POST %s, service=%s, timeout=%s",
            url,
            service,
            timeout if timeout is not None else self.timeout,
        )

        try:
            http_resp = self._session.post(
                url,
                data=payload,
                headers=merged_headers,
                timeout=timeout if timeout is not None else self.timeout,
                verify=self.verify,
            )
        except requests.RequestException as e:
            logger.error("Network error (%s): %s", url, e)
            raise exceptions.GRPCRequestException(
                f"HTTP error while calling service: {e}"
            ) from e

        grpc_status, grpc_message = _grpc_status_from_http_response(http_resp)
        msg_bytes, body_trailers = decode_grpc_web_body(http_resp.content or b"")
        # Some servers put grpc-status only in trailer frames (not HTTP headers)
        if grpc_status is None and "grpc-status" in body_trailers:
            grpc_status = body_trailers["grpc-status"]
            grpc_message = body_trailers.get("grpc-message")

        if grpc_status is None:
            if http_resp.ok and msg_bytes is not None:
                grpc_status = "0"
            else:
                grpc_status = "2"

        if grpc_status != "0":
            logger.info(
                "response with grpc-status=%s, grpc-message=%r, http=%s, url=%s",
                grpc_status,
                _decode_grpc_message(grpc_message),
                http_resp.status_code,
                url,
            )

        parsed: Any = None
        if grpc_status == "0" and msg_bytes is not None:
            parsed = output_type()
            try:
                parsed.ParseFromString(msg_bytes)
            except DecodeError as e:
                logger.exception(
                    "Failed to parse response as %s", output_type.__name__
                )
                raise exceptions.GRPCRequestException(
                    f"Failed to parse response as message {output_type.__name__}"
                ) from e

        return GRPCWebResult(
            service=service,
            http_status_code=http_resp.status_code,
            grpc_status=grpc_status or "2",
            grpc_message=_decode_grpc_message(grpc_message),
            response_headers=dict(http_resp.headers),
            message=parsed,
            output_type=output_type,
        )

    def __enter__(self) -> GRPCWebSession:
        logger.debug("Session opened (base_url=%s)", self.base_url)
        return self

    def __exit__(self, *args: object) -> None:
        logger.debug("Closing HTTP session")
        self._session.close()


def _decode_grpc_message(raw: str | None) -> str | None:
    if raw is None:
        return None

    return unquote(raw)


def _grpc_status_from_http_response(resp: requests.Response) -> tuple[str | None, str | None]:
    h = {k.lower(): v for k, v in resp.headers.items()}
    return h.get("grpc-status"), h.get("grpc-message")


@dataclasses.dataclass
class GRPCWebResult:
    service: str
    http_status_code: int
    grpc_status: str
    grpc_message: str | None
    response_headers: dict[str, str]
    message: Any
    output_type: type
