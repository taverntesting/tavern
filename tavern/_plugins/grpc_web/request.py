from __future__ import annotations

import copy
import dataclasses
import functools
import logging

from box import Box
from tavern._core import exceptions
from tavern._core.dict_util import check_expected_keys, format_keys
from tavern._core.pytest.config import TestConfig
from tavern.request import BaseRequest

from tavern._plugins.grpc_web.client import GRPCWebResult, GRPCWebSession

logger = logging.getLogger(__name__)


def _format_request_spec(rspec: dict, test_block_config: TestConfig) -> dict:
    fspec = format_keys(rspec, test_block_config.variables)
    if "json" in rspec:
        if "body" in rspec:
            raise exceptions.BadSchemaError(
                "grpc_web_request can contain only one of: body or json"
            )
        fspec["body"] = copy.deepcopy(fspec.pop("json"))

    return fspec


@dataclasses.dataclass
class GRPCWebWrappedResult:
    result: GRPCWebResult


class GRPCWebRequest(BaseRequest):
    def __init__(self, session: GRPCWebSession, request_spec: dict, test_block_config: TestConfig) -> None:
        allowed = {"service", "body", "json", "timeout", "headers"}
        check_expected_keys(allowed, request_spec)

        grpc_args = _format_request_spec(request_spec, test_block_config)

        timeout = grpc_args.pop("timeout", None)
        headers = grpc_args.pop("headers", None)
        service = grpc_args["service"]
        body = grpc_args.get("body")

        self._prepared = functools.partial(
            session.call,
            service=service,
            body=body,
            timeout=timeout,
            headers=headers,
        )

        self._original_request_vars = format_keys(request_spec, test_block_config.variables)

    def run(self) -> GRPCWebWrappedResult:
        try:
            result = self._prepared()
            logger.debug(
                "request completed, http=%s, grpc-status=%s",
                result.http_status_code,
                result.grpc_status,
            )
            return GRPCWebWrappedResult(result=result)
        except ValueError as e:
            logger.exception("Error while executing request")
            raise exceptions.GRPCRequestException from e

    @property
    def request_vars(self) -> Box:
        return Box(self._original_request_vars)
