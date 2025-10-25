from unittest.mock import Mock

import pytest

from tavern._core import exceptions
from tavern._plugins.graphql.response import GraphQLResponse


class TestGraphQLResponse:
    def test_init_defaults(self, graphql_test_block_config):
        session = Mock()
        expected = {}

        response = GraphQLResponse(session, "test", expected, graphql_test_block_config)

        assert response.expected["status_code"] == 200

    def test_init_custom_status_code(self, graphql_test_block_config):
        session = Mock()
        expected = {"status_code": 201}

        response = GraphQLResponse(session, "test", expected, graphql_test_block_config)

        assert response.expected["status_code"] == 201

    def test_init_list_status_code(self, graphql_test_block_config):
        session = Mock()
        expected = {"status_code": [200, 201]}

        response = GraphQLResponse(session, "test", expected, graphql_test_block_config)

        assert response.expected["status_code"] == [200, 201]

    def test_str_with_response(self, graphql_test_block_config):
        session = Mock()
        expected = {}

        mock_response = Mock()
        mock_response.text = '{"data": {"hello": "world"}}'

        response = GraphQLResponse(session, "test", expected, graphql_test_block_config)
        response.response = mock_response

        assert str(response) == '{"data": {"hello": "world"}}'

    def test_str_without_response(self, graphql_test_block_config):
        session = Mock()
        expected = {}

        response = GraphQLResponse(session, "test", expected, graphql_test_block_config)

        assert str(response) == "<Not run yet>"

    def test_validate_response_format_valid_data(self, graphql_test_block_config):
        session = Mock()
        expected = {}

        mock_response = Mock()
        mock_response.json.return_value = {"data": {"hello": "world"}}

        response = GraphQLResponse(session, "test", expected, graphql_test_block_config)

        # Should not raise any exception
        response._validate_response_format(mock_response)

    def test_validate_response_format_valid_errors(self, graphql_test_block_config):
        session = Mock()
        expected = {}

        mock_response = Mock()
        mock_response.json.return_value = {
            "errors": [{"message": "Something went wrong"}]
        }

        response = GraphQLResponse(session, "test", expected, graphql_test_block_config)

        # Should not raise any exception, just log warning
        response._validate_response_format(mock_response)

    def test_validate_response_format_invalid_no_data_or_errors(
        self, graphql_test_block_config
    ):
        session = Mock()
        expected = {}

        mock_response = Mock()
        mock_response.json.return_value = {"other": "field"}

        response = GraphQLResponse(session, "test", expected, graphql_test_block_config)

        with pytest.raises(
            exceptions.BadSchemaError,
            match="GraphQL response must contain 'data' or 'errors' field",
        ):
            response._validate_response_format(mock_response)

    def test_validate_response_format_invalid_json(self, graphql_test_block_config):
        session = Mock()
        expected = {}

        mock_response = Mock()
        mock_response.json.side_effect = ValueError("Invalid JSON")

        response = GraphQLResponse(session, "test", expected, graphql_test_block_config)

        with pytest.raises(
            exceptions.BadSchemaError, match="Invalid JSON response: Invalid JSON"
        ):
            response._validate_response_format(mock_response)

    def test_verify_status_code_single_match(self, graphql_test_block_config):
        session = Mock()
        expected = {"status_code": 200}

        mock_response = Mock()
        mock_response.status_code = 200

        response = GraphQLResponse(session, "test", expected, graphql_test_block_config)

        # Should not raise any exception
        response._verify_status_code(mock_response)

    def test_verify_status_code_single_mismatch(self, graphql_test_block_config):
        session = Mock()
        expected = {"status_code": 200}

        mock_response = Mock()
        mock_response.status_code = 404

        response = GraphQLResponse(session, "test", expected, graphql_test_block_config)

        response._verify_status_code(mock_response)
        assert len(response.errors) == 1
        assert "Status code 404 not equal to expected 200" in response.errors[0]

    def test_verify_status_code_list_match(self, graphql_test_block_config):
        session = Mock()
        expected = {"status_code": [200, 201]}

        mock_response = Mock()
        mock_response.status_code = 201

        response = GraphQLResponse(session, "test", expected, graphql_test_block_config)

        # Should not raise any exception
        response._verify_status_code(mock_response)

    def test_verify_status_code_list_mismatch(self, graphql_test_block_config):
        session = Mock()
        expected = {"status_code": [200, 201]}

        mock_response = Mock()
        mock_response.status_code = 404

        response = GraphQLResponse(session, "test", expected, graphql_test_block_config)

        response._verify_status_code(mock_response)
        assert len(response.errors) == 1
        assert "Status code 404 not in expected list [200, 201]" in response.errors[0]
