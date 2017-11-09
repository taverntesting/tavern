from unittest.mock import patch

import pytest

from tavern.request import TRequest, get_request_args
from tavern.util import exceptions


@pytest.fixture(name="req")
def fix_example_request():
    spec = {
        "url":  "{request_url:s}",
        "method":  "POST",
        "headers": {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization":  "Basic {test_auth_token:s}",
        },
        "data": {
            "a_thing":  "authorization_code",
            "code":  "{code:s}",
            "url":  "{callback_url:s}",
        },
    }

    return spec.copy()


class TestRequests:
    def test_unknown_fields(self, req, includes): 
        """Unkown args should raise an error
        """
        req["fodokfowe"] = "Hello"

        with pytest.raises(exceptions.UnexpectedKeysError):
            TRequest(req, includes)

    def test_missing_format(self, req, includes):
        """All format variables should be present
        """
        del includes["variables"]["code"]

        with pytest.raises(exceptions.MissingFormatError):
            TRequest(req, includes)

    def test_bad_get_body(self, req, includes):
        """Can't add a body with a GET request
        """
        req["method"] = "GET"

        with pytest.raises(exceptions.BadSchemaError):
            TRequest(req, includes)

    def test_session_called_no_redirects(self, req, includes):
        """Always disable redirects
        """

        with patch("tavern.request.requests.Session.request") as rmock:
            TRequest(req, includes).run()

        assert rmock.called
        assert rmock.call_args[1]["allow_redirects"] == False

    def test_default_method(self, req, includes):
        del req["method"]
        del req["data"]

        args = get_request_args(req, includes)

        assert args["method"] == "GET"

    @pytest.mark.parametrize("body_key", (
        "json",
        "data"
    ))
    def test_default_method_raises_with_body(self, req, includes, body_key):
        del req["method"]
        del req["data"]

        req[body_key] = {"a": "b"}

        with pytest.raises(exceptions.BadSchemaError):
            get_request_args(req, includes)

    def test_no_override_method(self, req, includes):
        req["method"] = "POST"

        args = get_request_args(req, includes)

        assert args["method"] == "POST"

    def test_default_content_type(self, req, includes):
        del req["headers"]["Content-Type"]

        args = get_request_args(req, includes)

        assert args["headers"]["content-type"] == "application/json"

    def test_no_override_content_type(self, req, includes):
        req["headers"]["Content-Type"] = "application/x-www-form-urlencoded"

        args = get_request_args(req, includes)

        assert args["headers"]["Content-Type"] == "application/x-www-form-urlencoded"

    def test_no_override_content_type_case_insensitive(self, req, includes):
        del req["headers"]["Content-Type"]
        req["headers"]["content-type"] = "application/x-www-form-urlencoded"

        args = get_request_args(req, includes)

        assert args["headers"]["content-type"] == "application/x-www-form-urlencoded"


class TestExtFunctions:

    def test_get_from_function(self, req, includes):
        """Make sure ext functions work in request

        This is a bit of a silly example because we're passing a dictionary
        instead of a string like it would be from the test, but it saves us
        having to define another external function just for this test
        """
        to_copy = {"thing": "value"}

        req["data"] = {
            "$ext": {
                "function": "copy:copy",
                "extra_args": [to_copy],
            }
        }

        args = get_request_args(req, includes)

        assert args["data"] == to_copy
