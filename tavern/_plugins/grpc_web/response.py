from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from typing import Any, Union

from google.protobuf import json_format
from tavern._core import exceptions
from tavern._core.dict_util import check_expected_keys
from tavern._core.exceptions import TestFailError
from tavern._core.pytest.config import TestConfig
from tavern._plugins.grpc_web.client import GRPCWebSession
from tavern._plugins.grpc_web.request import GRPCWebWrappedResult
from tavern.response import BaseResponse

logger = logging.getLogger(__name__)

_GRPC_NAME_BY_CODE: dict[str, str] = {
    "0": "OK",
    "1": "CANCELLED",
    "2": "UNKNOWN",
    "3": "INVALID_ARGUMENT",
    "4": "DEADLINE_EXCEEDED",
    "5": "NOT_FOUND",
    "6": "ALREADY_EXISTS",
    "7": "PERMISSION_DENIED",
    "8": "RESOURCE_EXHAUSTED",
    "9": "FAILED_PRECONDITION",
    "10": "ABORTED",
    "11": "OUT_OF_RANGE",
    "12": "UNIMPLEMENTED",
    "13": "INTERNAL",
    "14": "UNAVAILABLE",
    "15": "DATA_LOSS",
    "16": "UNAUTHENTICATED",
}

_CODE_BY_NAME = {v: k for k, v in _GRPC_NAME_BY_CODE.items()}

StatusSpec = Union[str, int, list[str], list[int]]


def _normalize_status_list(spec: StatusSpec | None) -> list[str]:
    if spec is None:
        return ["0"]

    items: Sequence[str | int] = spec if isinstance(spec, list) else [spec]
    out: list[str] = []
    for item in items:
        # bool is an int subclass in Python, reject it explicitly to avoid interpreting YAML `true` as gRPC status code 1 (CANCELLED)
        if isinstance(item, bool):
            raise exceptions.GRPCServiceException(
                f"Unknown gRPC status code: {item!r}"
            )
        if isinstance(item, int):
            out.append(str(item))
        elif isinstance(item, str) and item.isdigit():
            out.append(str(int(item)))
        else:
            name = str(item).upper()
            if name not in _CODE_BY_NAME:
                raise exceptions.GRPCServiceException(
                    f"Unknown gRPC status code: {item!r}"
                )

            out.append(_CODE_BY_NAME[name])
    return out


class GRPCWebResponse(BaseResponse):
    def __init__(self, client: GRPCWebSession, name: str, expected: Mapping, test_block_config: TestConfig) -> None:
        check_expected_keys({"body", "status", "details", "save", "http_status_code", "verify_response_with"}, expected)
        super().__init__(name, expected, test_block_config)
        self._session = client

    def __str__(self) -> str:
        if self.response is None:
            return "<not executed yet>"

        r = self.response.result
        return (
            f"http {r.http_status_code} "
            f"grpc-status={r.grpc_status} ({_GRPC_NAME_BY_CODE.get(r.grpc_status, '?')})"
        )

    def _validate_block(self, blockname: str, block: Mapping) -> None:
        try:
            expected_block = self.expected["body"] or {}
        except KeyError:
            expected_block = {}

        if isinstance(expected_block, dict):
            # Keep backward compatibility warning without mutating expected body
            if expected_block.get("$ext"):
                logger.warning(
                    "In %s block, $ext is deprecated; use verify_response_with",
                    blockname,
                )

        test_strictness = self.test_block_config.strict
        block_strictness = test_strictness.option_for(blockname)
        self.recurse_check_key_match(expected_block, block, blockname, block_strictness)

    def verify(self, response: GRPCWebWrappedResult) -> Mapping:
        r = response.result
        logger.debug(
            "Verifying response for stage %s: http=%s, grpc-status=%s",
            self.name,
            r.http_status_code,
            r.grpc_status
        )

        verify_status = _normalize_status_list(self.expected.get("status"))
        if r.grpc_status not in verify_status:
            names = [_GRPC_NAME_BY_CODE.get(s, s) for s in verify_status]
            self._adderr(
                "Expected grpc-status to be one of %s (%s), got %s (%s)",
                verify_status,
                names,
                r.grpc_status,
                _GRPC_NAME_BY_CODE.get(r.grpc_status, r.grpc_status)
            )

        if "http_status_code" in self.expected:
            exp_http = self.expected["http_status_code"]
            if exp_http != r.http_status_code:
                self._adderr(
                    "Expected http status code %s, got %s",
                    exp_http,
                    r.http_status_code,
                )

        if "details" in self.expected:
            if self.expected["details"] != r.grpc_message:
                self._adderr(
                    "Expected grpc-message/details %r, got %r",
                    self.expected["details"],
                    r.grpc_message,
                )

        saved = self._handle_body(r) or {}

        if self.errors:
            raise TestFailError(
                f"Test {self.name:s} failed verification:\n{self._str_errors():s}",
                failures=self.errors
            )

        return saved

    def _handle_body(self, r: Any) -> dict[str, Any] | None:
        if r.grpc_status != "0":
            if "body" in self.expected:
                self._adderr("body field is set, but grpc-status is not OK (0)")
            return None

        if "body" not in self.expected:
            return {}

        if r.message is None:
            self._adderr("Expected protobuf response body, but message is empty")
            return None

        json_result = json_format.MessageToDict(
            r.message,
            # Keep output stable for Tavern matching/saving semantics
            always_print_fields_with_no_presence=True,
            preserving_proto_field_name=True,
        )

        expected_parsed = r.output_type()
        try:
            json_format.ParseDict(self.expected["body"], expected_parsed)
        except json_format.ParseError as e:
            self._adderr(f"Response body has invalid format: {e}", e=e)

        self._validate_block("json", json_result)
        self._maybe_run_validate_functions(json_result)

        saved: dict[str, Any] = {}
        saved.update(self.maybe_get_save_values_from_save_block("body", json_result))
        saved.update(self.maybe_get_save_values_from_ext(json_result, self.expected))

        return saved
