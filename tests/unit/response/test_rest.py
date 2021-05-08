from unittest.mock import Mock, patch

import pytest

from tavern._plugins.rest.response import RestResponse
from tavern.util import exceptions
from tavern.util.dict_util import format_keys
from tavern.util.loader import ANYTHING


@pytest.fixture(name="example_response")
def fix_example_response():
    spec = {
        "status_code": 302,
        "headers": {
            "Content-Type": "application/json",
            "location": "www.google.com?search=breadsticks",
        },
        "json": {"a_thing": "authorization_code", "code": "abc123"},
    }

    return spec.copy()


@pytest.fixture(name="nested_response")
def fix_nested_response():
    # https://github.com/taverntesting/tavern/issues/45
    spec = {
        "status_code": 200,
        "headers": {"Content-Type": "application/json"},
        "json": {"users": [{"u": {"user_id": "def456"}}]},
    }

    return spec.copy()


@pytest.fixture(name="nested_schema")
def fix_nested_schema():
    # https://github.com/taverntesting/tavern/issues/45
    spec = {
        "status_code": 200,
        "headers": {"Content-Type": "application/json"},
        "json": {"users": [{"u": {"user_id": "{code}"}}]},
    }

    return spec.copy()


class TestSave:
    def test_save_body(self, example_response, includes):
        """Save a key from the body into the right name"""
        example_response["save"] = {"json": {"test_code": "code"}}

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        saved = r.maybe_get_save_values_from_save_block(
            "json", example_response["json"]
        )

        assert saved == {"test_code": example_response["json"]["code"]}

    def test_save_body_nested(self, example_response, includes):
        """Save a key from the body into the right name"""
        example_response["json"]["nested"] = {"subthing": "blah"}
        example_response["save"] = {"json": {"test_nested_thing": "nested.subthing"}}

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        saved = r.maybe_get_save_values_from_save_block(
            "json", example_response["json"]
        )

        assert saved == {
            "test_nested_thing": example_response["json"]["nested"]["subthing"]
        }

    def test_save_body_nested_list(self, example_response, includes):
        """Save a key from the body into the right name"""
        example_response["json"]["nested"] = {"subthing": ["abc", "def"]}
        example_response["save"] = {"json": {"test_nested_thing": "nested.subthing[0]"}}

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        saved = r.maybe_get_save_values_from_save_block(
            "json", example_response["json"]
        )

        assert saved == {
            "test_nested_thing": example_response["json"]["nested"]["subthing"][0]
        }

    def test_save_header(self, example_response, includes):
        """Save a key from the headers into the right name"""
        example_response["save"] = {"headers": {"next_location": "location"}}

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        saved = r.maybe_get_save_values_from_save_block(
            "headers", example_response["headers"]
        )

        assert saved == {"next_location": example_response["headers"]["location"]}

    def test_save_redirect_query_param(self, example_response, includes):
        """Save a key from the query parameters of the redirect location"""
        example_response["save"] = {"redirect_query_params": {"test_search": "search"}}

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        saved = r.maybe_get_save_values_from_save_block(
            "redirect_query_params", {"search": "breadsticks"}
        )

        assert saved == {"test_search": "breadsticks"}

    @pytest.mark.parametrize("save_from", ("json", "headers", "redirect_query_params"))
    def test_bad_save(self, save_from, example_response, includes):
        example_response["save"] = {save_from: {"abc": "123"}}

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        saved = r.maybe_get_save_values_from_save_block(save_from, {})

        assert not saved

        assert r.errors


class TestValidate:
    def test_simple_validate_body(self, example_response, includes):
        """Make sure a simple value comparison works"""

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        r._validate_block("json", example_response["json"])

        assert not r.errors

    def test_validate_list_body(self, example_response, includes):
        """Make sure a list response can be validated"""

        example_response["json"] = ["a", 1, "b"]

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        r._validate_block("json", example_response["json"])

        assert not r.errors

    def test_validate_list_body_wrong_order(self, example_response, includes):
        """Order of list items matters"""

        example_response["json"] = ["a", 1, "b"]

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        r._validate_block("json", example_response["json"][::-1])

        assert r.errors

    def test_validate_nested_body(self, example_response, includes):
        """Make sure a nested value comparison works"""

        example_response["json"]["nested"] = {"subthing": "blah"}

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        r._validate_block("json", example_response["json"])

        assert not r.errors

    def test_simple_validate_headers(self, example_response, includes):
        """Make sure a simple value comparison works"""

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        r._validate_block("headers", example_response["headers"])

        assert not r.errors

    def test_simple_validate_redirect_query_params(self, example_response, includes):
        """Make sure a simple value comparison works"""

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        r._validate_block("redirect_query_params", {"search": "breadsticks"})

        assert not r.errors

    def test_validate_missing_list_key(self, example_response, includes):
        """If we expect 4 items and 3 were returned, catch error"""

        example_response["json"] = ["a", 1, "b", "c"]
        bad_expected = example_response["json"][:-1]

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        r._validate_block("json", bad_expected)

        assert r.errors

    def test_validate_wrong_list_dict(self, example_response, includes):
        """We expected a list, but we got a dict in the response"""

        example_response["json"] = ["a", 1, "b", "c"]
        bad_expected = {"a": "b"}

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        r._validate_block("json", bad_expected)

        assert r.errors

    def test_validate_wrong_dict_list(self, example_response, includes):
        """We expected a dict, but we got a list in the response"""

        example_response["json"] = {"a": "b"}
        bad_expected = ["a", "b", "c"]

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        r._validate_block("json", bad_expected)

        assert r.errors


class TestMatchStatusCodes:
    def test_validate_single_status_code_passes(self, example_response, includes):
        """single status code match"""

        example_response["status_code"] = 100

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        r._check_status_code(100, {})

        assert not r.errors

    def test_validate_single_status_code_incorrect(self, example_response, includes):
        """single status code mismatch"""

        example_response["status_code"] = 100

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        r._check_status_code(102, {})

        assert r.errors

    def test_validate_multiple_status_codes_passes(self, example_response, includes):
        """Check it can match mutliple status codes"""

        example_response["status_code"] = [100, 200, 300]

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        r._check_status_code(100, {})

        assert not r.errors

    def test_validate_multiple_status_codes_missing(self, example_response, includes):
        """Status code was not in list"""

        example_response["status_code"] = [100, 200, 300]

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        r._check_status_code(103, {})

        assert r.errors


class TestNestedValidate:
    def test_validate_nested_null(self, example_response, includes):
        """Check that nested 'null' comparisons do not work"""

        example_response["json"] = {"nested": {"subthing": None}}

        expected = {"nested": {"subthing": "blah"}}

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        r._validate_block("json", expected)

        assert r.errors

    def test_validate_nested_anything(self, example_response, includes):
        """Check that nested 'anything' comparisons work

        This is a bit hacky because we're directly checking the ANYTHING
        comparison - need to add an integration test too
        """

        example_response["json"] = {"nested": {"subthing": ANYTHING}}

        expected = {"nested": {"subthing": "blah"}}

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        r._validate_block("json", expected)

        assert not r.errors


class TestFull:
    def test_validate_and_save(self, example_response, includes):
        """Test full verification + return saved values"""
        example_response["save"] = {"json": {"test_code": "code"}}
        r = RestResponse(Mock(), "Test 1", example_response, includes)

        class FakeResponse:
            headers = example_response["headers"]
            content = "test".encode("utf8")

            def json(self):
                return example_response["json"]

            status_code = example_response["status_code"]

        saved = r.verify(FakeResponse())

        assert saved == {"test_code": example_response["json"]["code"]}

    def test_incorrect_status_code(self, example_response, includes):
        """Test full verification + return saved values"""
        r = RestResponse(Mock(), "Test 1", example_response, includes)

        class FakeResponse:
            headers = example_response["headers"]
            content = "test".encode("utf8")

            def json(self):
                return example_response["json"]

            status_code = 400

        with pytest.raises(exceptions.TestFailError):
            r.verify(FakeResponse())

        assert r.errors

    def test_saved_value_in_validate(self, nested_response, nested_schema, includes):
        r = RestResponse(
            Mock(),
            "Test 1",
            format_keys(nested_schema, includes.variables),
            includes,
        )

        class FakeResponse:
            headers = nested_response["headers"]
            content = "test".encode("utf8")

            def json(self):
                return nested_response["json"]

            status_code = nested_response["status_code"]

        r.verify(FakeResponse())

    @pytest.mark.parametrize("value", [1, "some", False, None])
    def test_validate_single_value_response(self, example_response, includes, value):
        """Check validating single value response (string, int, etc)."""
        del example_response["json"]

        r = RestResponse(Mock(), "Test 1", example_response, includes)

        class FakeResponse:
            headers = example_response["headers"]
            content = "test".encode("utf8")

            def json(self):
                return value

            status_code = example_response["status_code"]

        r.verify(FakeResponse())


def test_status_code_warns(example_response, includes):
    """Should continue if the status code is nonexistent"""
    example_response["status_code"] = 231234

    with patch("tavern._plugins.rest.response.logger.warning") as wmock:
        RestResponse(Mock(), "Test 1", example_response, includes)

    assert wmock.called
