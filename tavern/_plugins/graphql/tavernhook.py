import logging
from collections.abc import Iterable
from os.path import abspath, dirname, join
from typing import Optional, Union

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
    response_block: Union[dict, Iterable[dict]],
    test_block_config: TestConfig,
    session: GraphQLClient,
) -> Optional[dict]:
    if response_block is None:
        return None

    expected: dict[str, list] = {"graphql_responses": []}
    if isinstance(response_block, dict):
        response_block = [response_block]

    for resp_block in response_block:
        f_expected = format_keys(resp_block, test_block_config.variables)
        expected["graphql_responses"].append(f_expected)

    return expected


# Schema validation
schema_path: str = join(abspath(dirname(__file__)), "jsonschema.yaml")
with open(schema_path, encoding="utf-8") as schema_file:
    schema = yaml.load(schema_file, Loader=yaml.SafeLoader)
