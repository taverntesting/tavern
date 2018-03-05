import pytest
from mock import Mock

from tavern.response import RestResponse
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


@pytest.fixture(name='nested_response')
def fix_nested_response():
    # https://github.com/taverntesting/tavern/issues/45
    spec = {
        "status_code": 200,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": {
            "users": [
                {
                    "u": {
                        "user_id": "def456"
                    }
                }
            ]
        }
    }

    return spec.copy()


@pytest.fixture(name='nested_schema')
def fix_nested_schema():
    # https://github.com/taverntesting/tavern/issues/45
    spec = {
        "status_code": 200,
        "headers": {
            "Content-Type": "application/json"
        },
        "body": {
            "users": [
                {
                    "u": {
                        "user_id": "{code}"
                    }
                }
            ]
        }
    }

    return spec.copy()


class TestSave:

    def test_save_body(self, resp, includes):
        """Save a key from the body into the right name
        """
        resp["save"] = {"body": {"test_code": "code"}}

        r = RestResponse(Mock(), "Test 1", resp, includes)

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

        r = RestResponse(Mock(), "Test 1", resp, includes)

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

        r = RestResponse(Mock(), "Test 1", resp, includes)

        saved = r._save_value("body", resp["body"])

        assert saved == {"test_nested_thing": resp["body"]["nested"]["subthing"][0]}

    def test_save_header(self, resp, includes):
        """Save a key from the headers into the right name
        """
        resp["save"] = {"headers": {"next_location": "location"}}

        r = RestResponse(Mock(), "Test 1", resp, includes)

        saved = r._save_value("headers", resp["headers"])

        assert saved == {"next_location": resp["headers"]["location"]}

    def test_save_redirect_query_param(self, resp, includes):
        """Save a key from the query parameters of the redirect location
        """
        resp["save"] = {"redirect_query_params": {"test_search": "search"}}

        r = RestResponse(Mock(), "Test 1", resp, includes)

        saved = r._save_value("redirect_query_params", {"search": "breadsticks"})

        assert saved == {"test_search": "breadsticks"}

    @pytest.mark.parametrize("save_from", (
        "body",
        "headers",
        "redirect_query_params",
    ))
    def test_bad_save(self, save_from, resp, includes):
        resp["save"] = {save_from: {"abc": "123"}}

        r = RestResponse(Mock(), "Test 1", resp, includes)

        saved = r._save_value(save_from, {})

        assert not saved

        assert r.errors


class TestValidate:

    def test_simple_validate_body(self, resp, includes):
        """Make sure a simple value comparison works
        """

        r = RestResponse(Mock(), "Test 1", resp, includes)

        r._validate_block("body", resp["body"])

        assert not r.errors

    def test_validate_list_body(self, resp, includes):
        """Make sure a list response can be validated
        """

        resp["body"] = ["a", 1, "b"]

        r = RestResponse(Mock(), "Test 1", resp, includes)

        r._validate_block("body", resp["body"])

        assert not r.errors

    def test_validate_list_body_wrong_order(self, resp, includes):
        """Order of list items matters
        """

        resp["body"] = ["a", 1, "b"]

        r = RestResponse(Mock(), "Test 1", resp, includes)

        r._validate_block("body", resp["body"][::-1])

        assert r.errors

    def test_validate_nested_body(self, resp, includes):
        """Make sure a nested value comparison works
        """
        
        resp["body"]["nested"] = { "subthing": "blah" }

        r = RestResponse(Mock(), "Test 1", resp, includes)

        r._validate_block("body", resp["body"])

        assert not r.errors

    def test_simple_validate_headers(self, resp, includes):
        """Make sure a simple value comparison works
        """

        r = RestResponse(Mock(), "Test 1", resp, includes)

        r._validate_block("headers", resp["headers"])

        assert not r.errors

    def test_simple_validate_redirect_query_params(self, resp, includes):
        """Make sure a simple value comparison works
        """

        r = RestResponse(Mock(), "Test 1", resp, includes)

        r._validate_block("redirect_query_params", {"search": "breadsticks"})

        assert not r.errors


class TestFull:

    def test_validate_and_save(self, resp, includes):
        """Test full verification + return saved values
        """
        resp["save"] = {"body": {"test_code": "code"}}
        r = RestResponse(Mock(), "Test 1", resp, includes)

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
        r = RestResponse(Mock(), "Test 1", resp, includes)

        class FakeResponse:
            headers = resp["headers"]
            content = "test".encode("utf8")
            def json(self):
                return resp["body"]
            status_code = 400

        with pytest.raises(exceptions.TestFailError):
            r.verify(FakeResponse())

        assert r.errors

    def test_saved_value_in_validate(self, nested_response, nested_schema,
                                     includes):
        r = RestResponse(Mock(), "Test 1", nested_schema, includes)

        class FakeResponse:
            headers = nested_response["headers"]
            content = "test".encode("utf8")
            def json(self):
                return nested_response["body"]
            status_code = nested_response["status_code"]

        r.verify(FakeResponse())
