import dataclasses

from tavern._plugins.graphql import tavernhook
from tavern._plugins.graphql.client import GraphQLClient


class TestTavernGraphQLPlugin:
    def test_plugin_properties(self):
        assert tavernhook.session_type == GraphQLClient
        assert tavernhook.request_block_name == "graphql_request"
        assert tavernhook.response_block_name == "graphql_response"

    def test_get_expected_from_request_with_response(self, graphql_test_block_config):
        response_block = {"status_code": 200}
        session = GraphQLClient()

        result = tavernhook.get_expected_from_request(
            response_block, graphql_test_block_config, session
        )

        assert result == {"graphql_responses": [{"status_code": 200}]}

    def test_get_expected_from_request_without_response(
        self, graphql_test_block_config
    ):
        response_block = None
        session = GraphQLClient()

        result = tavernhook.get_expected_from_request(
            response_block, graphql_test_block_config, session
        )

        assert result is None

    def test_get_expected_from_request_with_variables(self, graphql_test_block_config):
        response_block = {"status_code": 200, "data": {"user_id": "{user_id}"}}

        test_block_config = dataclasses.replace(
            graphql_test_block_config, variables={"user_id": "123"}
        )

        session = GraphQLClient()

        result = tavernhook.get_expected_from_request(
            response_block, test_block_config, session
        )

        assert result == {
            "graphql_responses": [{"status_code": 200, "data": {"user_id": "123"}}]
        }
