from __future__ import annotations

from os.path import abspath, dirname, join

import yaml
from tavern._core.dict_util import format_keys
from tavern._core.pytest.config import TestConfig

from tavern._plugins.grpc_web.client import GRPCWebSession
from tavern._plugins.grpc_web.request import GRPCWebRequest
from tavern._plugins.grpc_web.response import GRPCWebResponse

session_type = GRPCWebSession

request_type = GRPCWebRequest
request_block_name = "grpc_web_request"


def get_expected_from_request(response_block: dict, test_block_config: TestConfig, session: GRPCWebSession):
    return format_keys(response_block, test_block_config.variables)


verifier_type = GRPCWebResponse
response_block_name = "grpc_web_response"
has_multiple_responses = False

schema_path = join(abspath(dirname(__file__)), "jsonschema.yaml")
with open(schema_path, encoding="utf-8") as schema_file:
    schema = yaml.load(schema_file, Loader=yaml.SafeLoader)
