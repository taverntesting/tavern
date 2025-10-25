import logging
from os.path import abspath, dirname, join

import yaml

from tavern._core.dict_util import format_keys
from tavern._core.pytest.config import TestConfig

from .client import GraphQLClient
from .request import GraphQLRequest
from .response import GraphQLResponse

logger: logging.Logger = logging.getLogger(__name__)


session_type = GraphQLClient
request_type = GraphQLRequest
request_block_name = "graphql_request"
verifier_type = GraphQLResponse
response_block_name = "graphql_response"


def get_expected_from_request(
    response_block: dict, test_block_config: TestConfig, session: GraphQLClient
):
    if response_block is None:
        # GraphQL responses are optional for subscriptions
        return None

    f_expected = format_keys(response_block, test_block_config.variables)
    return f_expected


# Schema validation
schema_path: str = join(abspath(dirname(__file__)), "jsonschema.yaml")
with open(schema_path, encoding="utf-8") as schema_file:
    schema = yaml.load(schema_file, Loader=yaml.SafeLoader)
