from mock import patch, Mock
import requests

try:
    from urllib.parse import quote_plus
except ImportError:
    from urllib import quote_plus

import pytest

from tavern.request import RestRequest, get_request_args
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
            "array": [
                "{code:s}",
                "{code:s}",
            ]
        },
    }

    return spec.copy()


class TestRequests:
    def test_unknown_fields(self, req, includes):
        """Unkown args should raise an error
        """
        req["fodokfowe"] = "Hello"

        with pytest.raises(exceptions.UnexpectedKeysError):
            RestRequest(Mock(), req, includes)

    def test_missing_format(self, req, includes):
        """All format variables should be present
        """
        del includes["variables"]["code"]

        with pytest.raises(exceptions.MissingFormatError):
            RestRequest(Mock(), req, includes)

    def test_bad_get_body(self, req, includes):
        """Can't add a body with a GET request
        """
        req["method"] = "GET"

        with pytest.warns(RuntimeWarning):
            RestRequest(Mock(), req, includes)

    def test_session_called_no_redirects(self, req, includes):
        """Always disable redirects
        """

        rmock = Mock(spec=requests.Session)
        RestRequest(rmock, req, includes).run()

        assert rmock.request.called
        assert rmock.request.call_args[1]["allow_redirects"] == False

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

        with pytest.warns(RuntimeWarning):
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

    def test_nested_params_encoded(self, req, includes):
        req["params"] = {
            "a": {
                "b": {
                    "c": "d",
                }
            }
        }

        args = get_request_args(req, includes)

        assert args["params"]["a"] == "%7B%22b%22%3A+%7B%22c%22%3A+%22d%22%7D%7D"

    def test_array_substitution(self, req, includes):
        args = get_request_args(req, includes)

        assert args['data']['array'] == ['def456', 'def456']


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


class TestOptionalDefaults:

    @pytest.mark.parametrize("verify", (
        True,
        False
    ))
    def test_passthrough_verify(self, req, includes, verify):
        """Should be able to pass 'verify' through to requests.request
        """

        req["verify"] = verify

        args = get_request_args(req, includes)

        assert args["verify"] == verify
