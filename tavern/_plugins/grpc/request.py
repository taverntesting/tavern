import dataclasses
import functools
import json
import logging
import warnings
from typing import Union

import grpc
from box import Box

from tavern._core import exceptions
from tavern._core.dict_util import check_expected_keys, format_keys
from tavern._core.pytest.config import TestConfig
from tavern._plugins.grpc.client import GRPCClient
from tavern.request import BaseRequest

logger: logging.Logger = logging.getLogger(__name__)


def get_grpc_args(rspec: dict, test_block_config: TestConfig) -> dict:
    """Format GRPC request args"""

    fspec = format_keys(rspec, test_block_config.variables)

    # FIXME: Clarify 'json' and 'body' for grpc requests
    # FIXME 2: also it should allow proto text format. Maybe binary.
    if "json" in rspec:
        if "body" in rspec:
            raise exceptions.BadSchemaError(
                "Can only specify one of 'body' or 'json' in GRPC request"
            )

        fspec["body"] = json.dumps(fspec.pop("json"))

    return fspec


@dataclasses.dataclass
class WrappedFuture:
    response: Union[grpc.Call, grpc.Future]
    service_name: str


class GRPCRequest(BaseRequest):
    """Wrapper for a single GRPC request on a client

    Similar to RestRequest, publishes a single message.
    """

    _warned = False

    def __init__(
        self, client: GRPCClient, request_spec: dict, test_block_config: TestConfig
    ) -> None:
        if not self._warned:
            warnings.warn(
                "Tavern gRPC support is experimental and will be updated in a future release.",
                RuntimeWarning,
                stacklevel=0,
            )
            GRPCRequest._warned = True

        expected = {"host", "service", "body"}

        check_expected_keys(expected, request_spec)

        grpc_args = get_grpc_args(request_spec, test_block_config)

        self._prepared = functools.partial(client.call, **grpc_args)

        self._service_name = grpc_args.get("service", None)

        # Need to do this here because get_publish_args will modify the original
        # input, which we might want to use to format. No error handling because
        # all the error handling is done in the previous call
        self._original_request_vars = format_keys(
            request_spec, test_block_config.variables
        )

    def run(self) -> WrappedFuture:
        try:
            return WrappedFuture(
                response=self._prepared(), service_name=self._service_name
            )
        except ValueError as e:
            logger.exception("Error executing request")
            raise exceptions.GRPCRequestException from e

    @property
    def request_vars(self) -> Box:
        return Box(self._original_request_vars)
