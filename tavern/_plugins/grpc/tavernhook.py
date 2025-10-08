"""
Tavern gRPC TavernHook Plugin

This module provides tavernhook functionality for gRPC requests in the Tavern testing framework.
It handles the integration between Tavern and the gRPC request system.

The module contains the tavernhook classes and functions that enable Tavern to
properly handle gRPC request execution and response processing.
"""

import logging
from os.path import abspath, dirname, join

import yaml

from tavern._core.dict_util import format_keys
from tavern._core.pytest.config import TestConfig

from .client import GRPCClient
from .request import GRPCRequest
from .response import GRPCResponse

logger: logging.Logger = logging.getLogger(__name__)


session_type = GRPCClient

request_type = GRPCRequest
request_block_name = "grpc_request"


def get_expected_from_request(
    response_block, test_block_config: TestConfig, session: GRPCClient
):
    """Get expected response from gRPC request configuration.

    Args:
        response_block: Response block configuration
        test_block_config: Test configuration
        session: gRPC client session

    Returns:
        Formatted expected response configuration
    """
    f_expected = format_keys(response_block, test_block_config.variables)
    expected = f_expected

    return expected


verifier_type = GRPCResponse
response_block_name = "grpc_response"

schema_path: str = join(abspath(dirname(__file__)), "jsonschema.yaml")
with open(schema_path) as schema_file:
    schema = yaml.load(schema_file, Loader=yaml.SafeLoader)
