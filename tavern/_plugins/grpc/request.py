import functools
import json
import logging
from typing import Mapping

from box import Box

from tavern._core import exceptions
from tavern._core.dict_util import check_expected_keys, format_keys
from tavern._core.pytest.config import TestConfig
from tavern._plugins.grpc.client import GRPCClient
from tavern.request import BaseRequest

logger = logging.getLogger(__name__)


def get_grpc_args(rspec, test_block_config):
    """Format GRPC request args"""

    fspec = format_keys(rspec, test_block_config.variables)

    if "json" in rspec:
        if "body" in rspec:
            raise exceptions.BadSchemaError(
                "Can only specify one of 'body' or 'json' in GRPC request"
            )

        fspec["body"] = json.dumps(fspec.pop("json"))

    return fspec


class GRPCRequest(BaseRequest):
    """Wrapper for a single GRPC request on a client

    Similar to RestRequest, publishes a single message.
    """

    def __init__(
        self, client: GRPCClient, rspec: Mapping, test_block_config: TestConfig
    ):
        expected = {"host", "retain", "service", "body", "json"}

        check_expected_keys(expected, rspec)

        grpc_args = get_grpc_args(rspec, test_block_config)

        self._prepared = functools.partial(client.call, **grpc_args)

        # Need to do this here because get_publish_args will modify the original
        # input, which we might want to use to format. No error handling because
        # all the error handling is done in the previous call
        self._original_publish_args = format_keys(rspec, test_block_config.variables)

    def run(self):
        try:
            return self._prepared()
        except ValueError as e:
            logger.exception("Error executing request")
            raise exceptions.GRPCRequestException from e

    @property
    def request_vars(self):
        return Box(self._original_publish_args)
