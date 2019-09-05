import logging

from os.path import join, abspath, dirname

import yaml

from tavern.util.dict_util import format_keys

from .request import GRPCRequest
from .response import GRPCResponse
from .client import GRPCClient

logger = logging.getLogger(__name__)


session_type = GRPCClient

request_type = GRPCRequest
request_block_name = "grpc_request"


def get_expected_from_request(stage, test_block_config, session):
    # pylint: disable=unused-argument
    # grpc response is not required
    grpc_expected = stage.get("grpc_response")
    if grpc_expected:
        # format so we can subscribe to the right topic
        f_expected = format_keys(grpc_expected, test_block_config["variables"])
        expected = f_expected
    else:
        expected = {}

    return expected


verifier_type = GRPCResponse
response_block_name = "grpc_response"

schema_path = join(abspath(dirname(__file__)), "schema.yaml")
with open(schema_path, "r") as schema_file:
    schema = yaml.load(schema_file, Loader=yaml.SafeLoader)
