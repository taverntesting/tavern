import pytest

from tavern.response import TResponse
from tavern.util import exceptions


@pytest.fixture(name="resp")
def fix_example_response():
    spec = {
        "status_code": 302,
        "headers": {
            "Content-Type": "application/json",
            "location": "www.google.com?search=breadsticks",
        },
        "body": {
            "a_thing":  "authorization_code",
            "code":  "abc123",
        },
    }

    return spec.copy()


class TestSave:

    def test_save_body(self, resp, includes):
        """Save a key from the body into the right name
        """
        resp["save"] = {"body": {"test_code": "code"}}

        r = TResponse("Test 1", resp, includes)

        saved = r._save_value("body", resp["body"])

        assert saved == {"test_code": resp["body"]["code"]}

    def test_save_body_nested(self, resp, includes):
        """Save a key from the body into the right name
        """
        resp["body"]["nested"] = {
            "subthing": "blah"
        }
        resp["save"] = {
            "body": {
                "test_nested_thing": "nested.subthing"
            }
        }

        r = TResponse("Test 1", resp, includes)

        saved = r._save_value("body", resp["body"])

        assert saved == {"test_nested_thing": resp["body"]["nested"]["subthing"]}

    def test_save_body_nested_list(self, resp, includes):
        """Save a key from the body into the right name
        """
        resp["body"]["nested"] = {
            "subthing": [
                "abc",
                "def",
            ]
        }
        resp["save"] = {
            "body": {
                "test_nested_thing": "nested.subthing.0"
            }
        }

        r = TResponse("Test 1", resp, includes)

        saved = r._save_value("body", resp["body"])

        assert saved == {"test_nested_thing": resp["body"]["nested"]["subthing"][0]}

    def test_save_header(self, resp, includes):
        """Save a key from the headers into the right name
        """
        resp["save"] = {"headers": {"next_location": "location"}}

        r = TResponse("Test 1", resp, includes)

        saved = r._save_value("headers", resp["headers"])

        assert saved == {"next_location": resp["headers"]["location"]}

    def test_save_redirect_query_param(self, resp, includes):
        """Save a key from the query parameters of the redirect location
        """
        resp["save"] = {"redirect_query_params": {"test_search": "search"}}

        r = TResponse("Test 1", resp, includes)

        saved = r._save_value("redirect_query_params", {"search": "breadsticks"})

        assert saved == {"test_search": "breadsticks"}

    @pytest.mark.parametrize("save_from", (
        "body",
        "headers",
        "redirect_query_params",
    ))
    def test_bad_save(self, save_from, resp, includes):
        resp["save"] = {save_from: {"abc": "123"}}

        r = TResponse("Test 1", resp, includes)

        saved = r._save_value(save_from, {})

        assert not saved

        assert r.errors


class TestValidate:

    def test_simple_validate_body(self, resp, includes):
        """Make sure a simple value comparison works
        """

        r = TResponse("Test 1", resp, includes)

        r._validate_block("body", resp["body"])

        assert not r.errors

    def test_validate_list_body(self, resp, includes):
        """Make sure a list response can be validated
        """

        resp["body"] = ["a", 1, "b"]

        r = TResponse("Test 1", resp, includes)

        r._validate_block("body", resp["body"])

        assert not r.errors

    def test_validate_list_body_wrong_order(self, resp, includes):
        """Order of list items matters
        """

        resp["body"] = ["a", 1, "b"]

        r = TResponse("Test 1", resp, includes)

        r._validate_block("body", resp["body"][::-1])

        assert r.errors

    def test_validate_nested_body(self, resp, includes):
        """Make sure a nested value comparison works
        """
        
        resp["body"]["nested"] = { "subthing": "blah" }

        r = TResponse("Test 1", resp, includes)

        r._validate_block("body", resp["body"])

        assert not r.errors

    def test_simple_validate_headers(self, resp, includes):
        """Make sure a simple value comparison works
        """

        r = TResponse("Test 1", resp, includes)

        r._validate_block("headers", resp["headers"])

        assert not r.errors

    def test_simple_validate_redirect_query_params(self, resp, includes):
        """Make sure a simple value comparison works
        """

        r = TResponse("Test 1", resp, includes)

        r._validate_block("redirect_query_params", {"search": "breadsticks"})

        assert not r.errors


class TestFull:

    def test_validate_and_save(self, resp, includes):
        """Test full verification + return saved values
        """
        resp["save"] = {"body": {"test_code": "code"}}
        r = TResponse("Test 1", resp, includes)

        class FakeResponse:
            headers = resp["headers"]
            content = "test".encode("utf8")
            def json(self):
                return resp["body"]
            status_code = resp["status_code"]

        saved = r.verify(FakeResponse())

        assert saved == {"test_code": resp["body"]["code"]}

    def test_incorrect_status_code(self, resp, includes):
        """Test full verification + return saved values
        """
        r = TResponse("Test 1", resp, includes)

        class FakeResponse:
            headers = resp["headers"]
            content = "test".encode("utf8")
            def json(self):
                return resp["body"]
            status_code = 400

        with pytest.raises(exceptions.TestFailError):
            r.verify(FakeResponse())

        assert r.errors
