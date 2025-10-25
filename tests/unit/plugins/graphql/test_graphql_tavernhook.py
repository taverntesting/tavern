from unittest.mock import Mock

from tavern._core.pytest.config import TavernInternalConfig, TestConfig
from tavern._core.strict_util import StrictLevel
from tavern._plugins.graphql.client import GraphQLClient
from tavern._plugins.graphql.tavernhook import TavernGraphQLPlugin


class TestTavernGraphQLPlugin:
    def test_plugin_properties(self):
        assert TavernGraphQLPlugin.session_type == GraphQLClient
        assert TavernGraphQLPlugin.request_block_name == "graphql_request"
        assert TavernGraphQLPlugin.response_block_name == "graphql_response"

    def test_get_expected_from_request_with_response(self):
        response_block = {"status_code": 200}
        test_block_config = TestConfig(
            variables={},
            strict=StrictLevel.all_on(),
            tavern_internal=TavernInternalConfig(
                pytest_hook_caller=Mock(),
                backends={"graphql": "graphql"},
            ),
            follow_redirects=False,
            stages=[],
        )
        session = GraphQLClient()

        result = TavernGraphQLPlugin.get_expected_from_request(
            response_block, test_block_config, session
        )

        assert result == {"status_code": 200}

    def test_get_expected_from_request_without_response(self):
        response_block = None
        test_block_config = TestConfig(
            variables={},
            strict=StrictLevel.all_on(),
            tavern_internal=TavernInternalConfig(
                pytest_hook_caller=Mock(),
                backends={"graphql": "graphql"},
            ),
            follow_redirects=False,
            stages=[],
        )
        session = GraphQLClient()

        result = TavernGraphQLPlugin.get_expected_from_request(
            response_block, test_block_config, session
        )

        assert result is None

    def test_get_expected_from_request_with_variables(self):
        response_block = {"status_code": 200, "data": {"user_id": "{user_id}"}}
        test_block_config = TestConfig(
            variables={"user_id": "123"},
            strict=StrictLevel.all_on(),
            tavern_internal=TavernInternalConfig(
                pytest_hook_caller=Mock(),
                backends={"graphql": "graphql"},
            ),
            follow_redirects=False,
            stages=[],
        )
        session = GraphQLClient()

        result = TavernGraphQLPlugin.get_expected_from_request(
            response_block, test_block_config, session
        )

        assert result == {"status_code": 200, "data": {"user_id": "123"}}

    def test_schema_loaded(self):
        from tavern._plugins.graphql.tavernhook import schema

        assert schema is not None
        assert isinstance(schema, dict)
        assert "properties" in schema
        assert "graphql" in schema["properties"]
