import copy
from unittest.mock import Mock

import pytest

from tavern._core.pytest.config import TavernInternalConfig, TestConfig
from tavern._core.strict_util import StrictLevel

# GraphQL-specific configuration
_graphql_includes = TestConfig(
    variables={},
    strict=StrictLevel.all_on(),
    tavern_internal=TavernInternalConfig(
        pytest_hook_caller=Mock(),
        backends={"graphql": "gql"},
    ),
    follow_redirects=False,
    stages=[],
)


@pytest.fixture(scope="function", name="graphql_test_block_config")
def graphql_test_block_config_fixture():
    """Test block configuration for GraphQL tests."""
    return copy.deepcopy(_graphql_includes)
