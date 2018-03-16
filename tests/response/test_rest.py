import pytest
from mock import Mock, patch

from tavern.response import RestResponse
from tavern.util.loader import ANYTHING
from tavern.util import exceptions


@pytest.fixture(name="example_response")
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

    def test_save_body(self, example_response, includes):
        """Save a key from the body into the right name
        """
        example_response["save"] = {"body": {"test_code": "code"}}

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        saved = r._save_value("body", example_response["body"])

        assert saved == {"test_code": example_response["body"]["code"]}

    def test_save_body_nested(self, example_response, includes):
        """Save a key from the body into the right name
        """
        example_response["body"]["nested"] = {
            "subthing": "blah"
        }
        example_response["save"] = {
            "body": {
                "test_nested_thing": "nested.subthing"
            }
        }

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        saved = r._save_value("body", example_response["body"])

        assert saved == {"test_nested_thing": example_response["body"]["nested"]["subthing"]}

    def test_save_body_nested_list(self, example_response, includes):
        """Save a key from the body into the right name
        """
        example_response["body"]["nested"] = {
            "subthing": [
                "abc",
                "def",
            ]
        }
        example_response["save"] = {
            "body": {
                "test_nested_thing": "nested.subthing.0"
            }
        }

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        saved = r._save_value("body", example_response["body"])

        assert saved == {"test_nested_thing": example_response["body"]["nested"]["subthing"][0]}

    def test_save_header(self, example_response, includes):
        """Save a key from the headers into the right name
        """
        example_response["save"] = {"headers": {"next_location": "location"}}

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        saved = r._save_value("headers", example_response["headers"])

        assert saved == {"next_location": example_response["headers"]["location"]}

    def test_save_redirect_query_param(self, example_response, includes):
        """Save a key from the query parameters of the redirect location
        """
        example_response["save"] = {"redirect_query_params": {"test_search": "search"}}

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        saved = r._save_value("redirect_query_params", {"search": "breadsticks"})

        assert saved == {"test_search": "breadsticks"}

    @pytest.mark.parametrize("save_from", (
        "body",
        "headers",
        "redirect_query_params",
    ))
    def test_bad_save(self, save_from, example_response, includes):
        example_response["save"] = {save_from: {"abc": "123"}}

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        saved = r._save_value(save_from, {})

        assert not saved

        assert r.errors


class TestValidate:

    def test_simple_validate_body(self, example_response, includes):
        """Make sure a simple value comparison works
        """

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        r._validate_block("body", example_response["body"])

        assert not r.errors

    def test_validate_list_body(self, example_response, includes):
        """Make sure a list response can be validated
        """

        example_response["body"] = ["a", 1, "b"]

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        r._validate_block("body", example_response["body"])

        assert not r.errors

    def test_validate_list_body_wrong_order(self, example_response, includes):
        """Order of list items matters
        """

        example_response["body"] = ["a", 1, "b"]

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        r._validate_block("body", example_response["body"][::-1])

        assert r.errors

    def test_validate_nested_body(self, example_response, includes):
        """Make sure a nested value comparison works
        """

        example_response["body"]["nested"] = { "subthing": "blah" }

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        r._validate_block("body", example_response["body"])

        assert not r.errors

    def test_simple_validate_headers(self, example_response, includes):
        """Make sure a simple value comparison works
        """

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        r._validate_block("headers", example_response["headers"])

        assert not r.errors

    def test_simple_validate_redirect_query_params(self, example_response, includes):
        """Make sure a simple value comparison works
        """

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        r._validate_block("redirect_query_params", {"search": "breadsticks"})

        assert not r.errors


class TestNestedValidate:

    def test_validate_nested_null(self, example_response, includes):
        """Check that nested 'null' comparisons work

        This will be removed in a future version
        """

        example_response["body"] = {
            "nested": {
                "subthing": None
            }
        }

        expected = {
            "nested": {
                "subthing": "blah",
            }
        }

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        with pytest.warns(FutureWarning):
            r._validate_block("body", expected)

        assert not r.errors

    def test_validate_nested_anything(self, example_response, includes):
        """Check that nested 'anything' comparisons work

        This is a bit hacky because we're directly checking the ANYTHING
        comparison - need to add an integration test too
        """

        example_response["body"] = {
            "nested": {
                "subthing": ANYTHING,
            }
        }

        expected = {
            "nested": {
                "subthing": "blah",
            }
        }

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        r._validate_block("body", expected)

        assert not r.errors


class TestFull:

    def test_validate_and_save(self, example_response, includes):
        """Test full verification + return saved values
        """
        example_response["save"] = {"body": {"test_code": "code"}}
        r = RestResponse(Mock(), "Test 1", example_response, includes)

        class FakeResponse:
            headers = example_response["headers"]
            content = "test".encode("utf8")
            def json(self):
                return example_response["body"]
            status_code = example_response["status_code"]

        saved = r.verify(FakeResponse())

        assert saved == {"test_code": example_response["body"]["code"]}

    def test_incorrect_status_code(self, example_response, includes):
        """Test full verification + return saved values
        """
        r = RestResponse(Mock(), "Test 1", example_response, includes)

        class FakeResponse:
            headers = example_response["headers"]
            content = "test".encode("utf8")
            def json(self):
                return example_response["body"]
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


def test_status_code_warns(example_response, includes):
    """Should continue if the status code is nonexistent
    """
    example_response["status_code"] = 231234

    with patch("tavern.response.rest.logger.warning") as wmock:
        RestResponse(Mock(), "Test 1", example_response, includes)

    assert wmock.called
