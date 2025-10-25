from unittest.mock import Mock

import requests

from tavern._plugins.graphql.client import GraphQLClient
from tavern._plugins.graphql.response import GraphQLResponse


class TestGraphQLResponse:
    def test_init_defaults(self, graphql_test_block_config):
        session = Mock(spec=GraphQLClient)
        expected = {}

        response = GraphQLResponse(session, "test", expected, graphql_test_block_config)

        assert response.expected["status_code"] == 200

    def test_init_custom_status_code(self, graphql_test_block_config):
        session = Mock(spec=GraphQLClient)
        expected = {"status_code": 201}

        response = GraphQLResponse(session, "test", expected, graphql_test_block_config)

        assert response.expected["status_code"] == 201

    def test_init_list_status_code(self, graphql_test_block_config):
        session = Mock(spec=GraphQLClient)
        expected = {"status_code": [200, 201]}

        response = GraphQLResponse(session, "test", expected, graphql_test_block_config)

        assert response.expected["status_code"] == [200, 201]

    def test_str_with_response(self, graphql_test_block_config):
        session = Mock(spec=GraphQLClient)
        expected = {}

        mock_response = Mock(spec=requests.Response)
        mock_response.text = '{"data": {"hello": "world"}}'

        response = GraphQLResponse(session, "test", expected, graphql_test_block_config)
        response.response = mock_response

        assert str(response) == '{"data": {"hello": "world"}}'

    def test_str_without_response(self, graphql_test_block_config):
        session = Mock(spec=GraphQLClient)
        expected = {}

        response = GraphQLResponse(session, "test", expected, graphql_test_block_config)

        assert str(response) == "<Not run yet>"

    def test_validate_response_format_valid_data(self, graphql_test_block_config):
        session = Mock(spec=GraphQLClient)
        expected = {}

        response = GraphQLResponse(session, "test", expected, graphql_test_block_config)

        # Should not raise any exception
        response._validate_graphql_response_structure({"data": {"hello": "world"}})
        assert len(response.errors) == 0

    def test_validate_response_format_valid_errors(self, graphql_test_block_config):
        session = Mock(spec=GraphQLClient)
        expected = {}

        response = GraphQLResponse(session, "test", expected, graphql_test_block_config)

        # Should not raise any exception, just log warning
        response._validate_graphql_response_structure(
            {"errors": [{"message": "Something went wrong"}]}
        )
        assert len(response.errors) == 0

    def test_validate_response_format_invalid_no_data_or_errors(
        self, graphql_test_block_config
    ):
        session = Mock(spec=GraphQLClient)
        expected = {}

        response = GraphQLResponse(session, "test", expected, graphql_test_block_config)

        response._validate_graphql_response_structure({"other": "field"})
        assert len(response.errors) == 2
        assert (
            "Response must contain either 'data' or 'errors' at the top level"
            in response.errors[0]
        )
        assert (
            "Invalid GraphQL top-level keys: {'other'}. Only 'data' and 'errors' are allowed"
            in response.errors[1]
        )
