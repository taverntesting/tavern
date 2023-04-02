import logging
from os.path import abspath, dirname, join

import yaml

from tavern._core.dict_util import format_keys

from .client import GRPCClient
from .request import GRPCRequest
from .response import GRPCResponse

logger = logging.getLogger(__name__)


session_type = GRPCClient

request_type = GRPCRequest
request_block_name = "grpc_request"


def get_expected_from_request(response_block, test_block_config, session):
    # format so we can subscribe to the right topic
    f_expected = format_keys(response_block, test_block_config.variables)
    expected = f_expected

    return expected


verifier_type = GRPCResponse
response_block_name = "grpc_response"

schema_path = join(abspath(dirname(__file__)), "jsonschema.yaml")
with open(schema_path, "r") as schema_file:
    schema = yaml.load(schema_file, Loader=yaml.SafeLoader)