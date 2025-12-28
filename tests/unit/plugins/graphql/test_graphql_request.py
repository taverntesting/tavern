from unittest.mock import Mock, patch

import pytest
from gql import FileVar

from tavern._core import exceptions
from tavern._plugins.graphql.client import GraphQLClient, GraphQLResponseLike
from tavern._plugins.graphql.request import GraphQLRequest, get_file_arguments


class TestGraphQLRequest:
    def test_init_valid_request(self, graphql_test_block_config):
        session = GraphQLClient()
        rspec = {
            "url": "http://example.com/graphql",
            "query": "query { hello }",
            "variables": {"name": "world"},
        }

        request = GraphQLRequest(session, rspec, graphql_test_block_config)

        assert request.request_vars.url == "http://example.com/graphql"
        assert request.request_vars.query == "query { hello }"
        assert request.request_vars.variables == {"name": "world"}

    def test_init_missing_query(self, graphql_test_block_config):
        session = GraphQLClient()
        rspec = {"url": "http://example.com/graphql", "variables": {"name": "world"}}

        with pytest.raises(
            exceptions.MissingKeysError,
            match="GraphQL request must contain 'query' field",
        ):
            GraphQLRequest(session, rspec, graphql_test_block_config)

    def test_init_missing_url(self, graphql_test_block_config):
        session = GraphQLClient()
        rspec = {"query": "query { hello }", "variables": {"name": "world"}}

        with pytest.raises(
            exceptions.MissingKeysError,
            match="GraphQL request must contain 'url' field",
        ):
            GraphQLRequest(session, rspec, graphql_test_block_config)

    def test_request_vars_defaults(self, graphql_test_block_config):
        session = GraphQLClient()
        rspec = {"url": "http://example.com/graphql", "query": "query { hello }"}

        request = GraphQLRequest(session, rspec, graphql_test_block_config)

        assert request.request_vars.variables == {}
        assert request.request_vars.operation_name is None
        assert request.request_vars.headers == {}

    def test_run_success(self, graphql_test_block_config):
        with (
            patch.object(GraphQLClient, "make_request") as mock_make_request,
        ):
            mock_response = Mock(spec=GraphQLResponseLike)
            mock_response.text = '{"data": {"hello": "world"}}'
            mock_make_request.return_value = mock_response

            session = GraphQLClient()
            rspec = {
                "url": "http://example.com/graphql",
                "query": "query { hello }",
                "headers": {"Authorization": "Bearer token"},
            }

            request = GraphQLRequest(session, rspec, graphql_test_block_config)
            response = request.run()

            mock_make_request.assert_called_once_with(
                url="http://example.com/graphql",
                query="query { hello }",
                variables={},
                operation_name=None,
                headers={
                    "Content-Type": "application/json",
                    "Authorization": "Bearer token",
                },
                has_files=False,
            )
            assert response.text == '{"data": {"hello": "world"}}'

    def test_run_failure(self, graphql_test_block_config):
        with patch.object(GraphQLClient, "make_request") as mock_make_request:
            mock_make_request.side_effect = Exception("Connection error")

            session = GraphQLClient()
            rspec = {"url": "http://example.com/graphql", "query": "query { hello }"}

            request = GraphQLRequest(session, rspec, graphql_test_block_config)

            with pytest.raises(
                exceptions.TavernException,
                match="GraphQL request failed: Connection error",
            ):
                request.run()


class TestGraphQLFileUploads:
    """Tests for GraphQL file upload functionality"""

    def test_get_file_arguments_single_file(self, graphql_test_block_config, tmp_path):
        """Test get_file_arguments with a single file"""
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        file_args = {"files": str(test_file)}

        result = get_file_arguments(file_args, graphql_test_block_config)

        # Should return a dict mapping 'files' to a FileVar
        assert "files" in result
        assert isinstance(result["files"], FileVar)

    def test_get_file_arguments_multiple_files(
        self, graphql_test_block_config, tmp_path
    ):
        """Test get_file_arguments with multiple files"""
        # Create test files
        test_file1 = tmp_path / "test1.txt"
        test_file1.write_text("test content 1")
        test_file2 = tmp_path / "test2.txt"
        test_file2.write_text("test content 2")

        file_args = {
            "file1": str(test_file1),
            "file2": str(test_file2),
        }

        result = get_file_arguments(file_args, graphql_test_block_config)

        # Should return a dict mapping variable names to FileVar objects
        assert "file1" in result
        assert "file2" in result
        assert isinstance(result["file1"], FileVar)
        assert isinstance(result["file2"], FileVar)

    def test_get_file_arguments_with_content_type(
        self, graphql_test_block_config, tmp_path
    ):
        """Test get_file_arguments with content type specified"""
        # Create a test file
        test_file = tmp_path / "test.json"
        test_file.write_text('{"key": "value"}')

        file_args = {
            "files": {
                "file_path": str(test_file),
                "content_type": "application/json",
            }
        }

        result = get_file_arguments(file_args, graphql_test_block_config)

        # Should return a dict mapping 'files' to a FileVar
        assert "files" in result
        assert isinstance(result["files"], FileVar)

    def test_get_file_arguments_empty_dict(self, graphql_test_block_config):
        """Test get_file_arguments with empty dict"""
        file_args = {}

        result = get_file_arguments(file_args, graphql_test_block_config)

        # Should return empty dict when no files
        assert result == {}

    def test_run_with_files_parameter(self, graphql_test_block_config, tmp_path):
        """Test running a GraphQL request with files parameter"""
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        with (
            patch.object(GraphQLClient, "make_request") as mock_make_request,
        ):
            mock_response = Mock(spec=GraphQLResponseLike)
            mock_response.text = '{"data": {"upload": "success"}}'
            mock_make_request.return_value = mock_response

            session = GraphQLClient()
            rspec = {
                "url": "http://example.com/graphql",
                "query": "mutation($files: Upload!) { singleUpload(file: $files) { id } }",
                "files": {"files": str(test_file)},
            }

            request = GraphQLRequest(session, rspec, graphql_test_block_config)
            response = request.run()

            # Verify that make_request was called
            mock_make_request.assert_called_once()

            # Get the call arguments
            call_args = mock_make_request.call_args

            # Check that variables include the files
            assert "variables" in call_args.kwargs
            variables = call_args.kwargs["variables"]
            assert "files" in variables
            assert isinstance(variables["files"], FileVar)

            assert response.text == '{"data": {"upload": "success"}}'

    def test_run_with_files_and_variables(self, graphql_test_block_config, tmp_path):
        """Test running a GraphQL request with both files and variables"""
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_text("test content")

        with (
            patch.object(GraphQLClient, "make_request") as mock_make_request,
        ):
            mock_response = Mock(spec=GraphQLResponseLike)
            mock_response.text = '{"data": {"upload": "success"}}'
            mock_make_request.return_value = mock_response

            session = GraphQLClient()
            rspec = {
                "url": "http://example.com/graphql",
                "query": "mutation($file: Upload!, $title: String!) { uploadFile(file: $file, title: $title) { id } }",
                "files": {"file": str(test_file)},
                "variables": {"title": "My Upload"},
            }

            request = GraphQLRequest(session, rspec, graphql_test_block_config)
            response = request.run()

            # Verify that make_request was called
            mock_make_request.assert_called_once()

            # Get the call arguments
            call_args = mock_make_request.call_args

            # Check that variables include both the files and the regular variables
            assert "variables" in call_args.kwargs
            variables = call_args.kwargs["variables"]
            assert "file" in variables
            assert "title" in variables
            assert variables["title"] == "My Upload"
            assert isinstance(variables["file"], FileVar)

            assert response.text == '{"data": {"upload": "success"}}'

    def test_run_with_multiple_files_and_metadata(
        self, graphql_test_block_config, tmp_path
    ):
        """Test running a GraphQL request with multiple files including metadata"""
        # Create test files
        test_file1 = tmp_path / "test1.txt"
        test_file1.write_text("test content 1")
        test_file2 = tmp_path / "test2.json"
        test_file2.write_text('{"key": "value"}')

        with (
            patch.object(GraphQLClient, "make_request") as mock_make_request,
        ):
            mock_response = Mock(spec=GraphQLResponseLike)
            mock_response.text = '{"data": {"upload": "success"}}'
            mock_make_request.return_value = mock_response

            session = GraphQLClient()
            rspec = {
                "url": "http://example.com/graphql",
                "query": "mutation($file1: Upload!, $file2: Upload!) { multipleUpload(file1: $file1, file2: $file2) { id } }",
                "files": {
                    "file1": str(test_file1),
                    "file2": {
                        "file_path": str(test_file2),
                        "content_type": "application/json",
                    },
                },
            }

            request = GraphQLRequest(session, rspec, graphql_test_block_config)
            response = request.run()

            # Verify that make_request was called
            mock_make_request.assert_called_once()

            # Get the call arguments
            call_args = mock_make_request.call_args

            # Check that variables include the files
            assert "variables" in call_args.kwargs
            variables = call_args.kwargs["variables"]
            assert "file1" in variables
            assert "file2" in variables
            assert isinstance(variables["file1"], FileVar)
            assert isinstance(variables["file2"], FileVar)

            assert response.text == '{"data": {"upload": "success"}}'
