from contextlib import ExitStack
import os
import tempfile
from unittest.mock import Mock

import attr
import pytest
import requests
from requests.cookies import RequestsCookieJar

from tavern._core import exceptions
from tavern._core.extfunctions import update_from_ext
from tavern._plugins.rest.request import (
    RestRequest,
    _check_allow_redirects,
    _get_file_arguments,
    _read_expected_cookies,
    get_request_args,
)


@pytest.fixture(name="req")
def fix_example_request():
    spec = {
        "url": "{request.prefix:s}{request.url:s}",
        "method": "POST",
        "headers": {
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": "Basic {test_auth_token:s}",
        },
        "data": {
            "a_thing": "authorization_code",
            "code": "{code:s}",
            "url": "{callback_url:s}",
            "array": ["{code:s}", "{code:s}"],
        },
    }

    return spec.copy()


class TestRequests(object):
    def test_unknown_fields(self, req, includes):
        """Unkown args should raise an error"""
        req["fodokfowe"] = "Hello"

        with pytest.raises(exceptions.UnexpectedKeysError):
            RestRequest(Mock(), req, includes)

    def test_missing_format(self, req, includes):
        """All format variables should be present"""
        del includes.variables["code"]

        with pytest.raises(exceptions.MissingFormatError):
            RestRequest(Mock(), req, includes)

    def test_bad_get_body(self, req, includes):
        """Can't add a body with a GET request"""
        req["method"] = "GET"

        with pytest.warns(RuntimeWarning):
            RestRequest(
                Mock(spec=requests.Session, cookies=RequestsCookieJar()), req, includes
            )


class TestHttpRedirects(object):
    def test_session_called_no_redirects(self, req, includes):
        """Always disable redirects by defauly"""

        assert _check_allow_redirects(req, includes) == False

    @pytest.mark.parametrize("do_follow", [True, False])
    def test_session_do_follow_redirects_based_on_test(self, req, includes, do_follow):
        """Locally enable following redirects in test"""

        req["follow_redirects"] = do_follow

        assert _check_allow_redirects(req, includes) == do_follow

    @pytest.mark.parametrize("do_follow", [True, False])
    def test_session_do_follow_redirects_based_on_global_flag(
        self, req, includes, do_follow
    ):
        """Globally enable following redirects in test"""

        includes = attr.evolve(includes, follow_redirects=do_follow)

        assert _check_allow_redirects(req, includes) == do_follow


class TestCookies(object):
    @pytest.fixture
    def mock_session(self):
        return Mock(spec=requests.Session, cookies=RequestsCookieJar())

    def test_no_expected_none_available(self, mock_session, req, includes):
        """No cookies expected and none available = OK"""

        req["cookies"] = []

        assert _read_expected_cookies(mock_session, req, includes) == {}

    def test_available_not_waited(self, req, includes):
        """some available but not set"""

        cookiejar = RequestsCookieJar()
        cookiejar.set("a", 2)
        mock_session = Mock(spec=requests.Session, cookies=cookiejar)

        assert _read_expected_cookies(mock_session, req, includes) == None

    def test_ask_for_nothing(self, req, includes):
        """explicitly ask fo rno cookies"""

        cookiejar = RequestsCookieJar()
        cookiejar.set("a", 2)
        mock_session = Mock(spec=requests.Session, cookies=cookiejar)

        req["cookies"] = []

        assert _read_expected_cookies(mock_session, req, includes) == {}

    def test_not_available_but_wanted(self, mock_session, req, includes):
        """Some wanted but not available"""

        req["cookies"] = ["a"]

        with pytest.raises(exceptions.MissingCookieError):
            _read_expected_cookies(mock_session, req, includes)

    def test_available_and_waited(self, req, includes):
        """some available and wanted"""

        cookiejar = RequestsCookieJar()
        cookiejar.set("a", 2)

        req["cookies"] = ["a"]

        mock_session = Mock(spec=requests.Session, cookies=cookiejar)

        assert _read_expected_cookies(mock_session, req, includes) == {"a": 2}

    def test_format_cookies(self, req, includes):
        """cookies in request should be formatted"""

        cookiejar = RequestsCookieJar()
        cookiejar.set("a", 2)

        req["cookies"] = ["{cookiename}"]
        includes.variables["cookiename"] = "a"

        mock_session = Mock(spec=requests.Session, cookies=cookiejar)

        assert _read_expected_cookies(mock_session, req, includes) == {"a": 2}

    def test_no_overwrite_cookie(self, req, includes):
        """cant redefine a cookie from previous request"""

        cookiejar = RequestsCookieJar()
        cookiejar.set("a", 2)

        req["cookies"] = ["a", {"a": "sjidfsd"}]

        mock_session = Mock(spec=requests.Session, cookies=cookiejar)

        with pytest.raises(exceptions.DuplicateCookieError):
            _read_expected_cookies(mock_session, req, includes)

    def test_no_duplicate_cookie(self, req, includes):
        """Can't override a cookiev alue twice"""

        cookiejar = RequestsCookieJar()

        req["cookies"] = [{"a": "sjidfsd"}, {"a": "fjhj"}]

        mock_session = Mock(spec=requests.Session, cookies=cookiejar)

        with pytest.raises(exceptions.DuplicateCookieError):
            _read_expected_cookies(mock_session, req, includes)


class TestRequestArgs(object):
    def test_default_method(self, req, includes):
        del req["method"]
        del req["data"]

        args = get_request_args(req, includes)

        assert args["method"] == "GET"

    @pytest.mark.parametrize("body_key", ("json", "data"))
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

    @pytest.mark.parametrize("extra", [{}, {"json": [1, 2, 3]}, {"data": {"a": 2}}])
    def test_no_default_content_type(self, req, includes, extra):
        del req["headers"]["Content-Type"]
        req.pop("json", {})
        req.pop("data", {})

        req.update(**extra)

        args = get_request_args(req, includes)

        # Requests will automatically set content type headers for json/form encoded data so we don't need to
        with pytest.raises(KeyError):
            assert args["headers"]["content-type"]

    def test_no_set_content_type(self, req, includes):
        del req["headers"]["Content-Type"]

        args = get_request_args(req, includes)

        with pytest.raises(KeyError):
            assert args["headers"]["content-type"]

    def test_cannot_send_data_and_json(self, req, includes):
        req["json"] = [1, 2, 3]
        req["data"] = [1, 2, 3]

        with pytest.raises(exceptions.BadSchemaError):
            get_request_args(req, includes)

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
        req["params"] = {"a": {"b": {"c": "d"}}}

        args = get_request_args(req, includes)

        assert args["params"]["a"] == "%7B%22b%22%3A+%7B%22c%22%3A+%22d%22%7D%7D"

    def test_array_substitution(self, req, includes):
        args = get_request_args(req, includes)

        assert args["data"]["array"] == ["def456", "def456"]

    def test_file_and_json_fails(self, req, includes):
        """Can't send json and files at once"""
        req["files"] = ["abc"]
        req["json"] = {"key": "value"}

        with pytest.raises(exceptions.BadSchemaError):
            get_request_args(req, includes)

    def test_file_and_data_succeeds(self, req, includes):
        """Can send form data and files at once"""
        req["files"] = ["abc"]

        get_request_args(req, includes)

    @pytest.mark.parametrize("extra_headers", ({}, {"x-cool-header": "plark"}))
    def test_headers_no_content_type_change(self, req, includes, extra_headers):
        """Sending a file doesn't set the content type as json"""
        del req["data"]
        req["files"] = ["abc"]

        args = get_request_args(req, includes)

        assert "content-type" not in [i.lower() for i in args["headers"].keys()]

    @pytest.mark.parametrize("cert_value", ("a", ("a", "b"), ["a", "b"]))
    def test_cert_with_valid_values(self, req, includes, cert_value):
        req["cert"] = cert_value
        args = get_request_args(req, includes)
        if isinstance(cert_value, list):
            assert args["cert"] == (cert_value[0], cert_value[1])
        else:
            assert args["cert"] == cert_value

    @pytest.mark.parametrize("verify_values", (True, False, "a"))
    def test_verity_with_valid_values(self, req, includes, verify_values):
        req["verify"] = verify_values
        args = get_request_args(req, includes)

        assert args["verify"] == verify_values


class TestExtFunctions:
    def test_get_from_function(self, req, includes):
        """Make sure ext functions work in request

        This is a bit of a silly example because we're passing a dictionary
        instead of a string like it would be from the test, but it saves us
        having to define another external function just for this test
        """
        to_copy = {"thing": "value"}
        original_json = {"test": "test"}

        req["json"] = {
            "$ext": {"function": "copy:copy", "extra_args": [to_copy]},
            **original_json,
        }

        update_from_ext(req, ["json"])

        assert req["json"] == dict(**to_copy, **original_json)


class TestOptionalDefaults:
    @pytest.mark.parametrize("verify", (True, False))
    def test_passthrough_verify(self, req, includes, verify):
        """Should be able to pass 'verify' through to requests.request"""

        req["verify"] = verify

        args = get_request_args(req, includes)

        assert args["verify"] == verify


class TestFileBody:
    def test_file_body(self, req, includes):
        """Test getting file body"""

        req.pop("data")
        req["file_body"] = "{callback_url}"

        args = get_request_args(req, includes)

        assert args["file_body"] == includes.variables["callback_url"]


class TestGetFiles(object):
    @pytest.fixture
    def mock_stack(self):
        return Mock(spec=ExitStack)

    def test_get_no_files(self, mock_stack, includes):
        """No files in request -> no files"""

        request_args = {}

        assert _get_file_arguments(request_args, mock_stack, includes) == {}

    def test_get_empty_files_list(self, mock_stack, includes):
        """No specific files specified -> no files"""

        request_args = {"files": {}}

        assert _get_file_arguments(request_args, mock_stack, includes) == {}

    def test_a_file(self, mock_stack, includes):
        """Json file should have the correct mimetype etc."""

        with tempfile.NamedTemporaryFile(suffix=".json") as tfile:
            request_args = {"files": {"file1": tfile.name}}

            file_spec = _get_file_arguments(request_args, mock_stack, includes)

        file = file_spec["files"]["file1"]
        assert file[0] == os.path.basename(tfile.name)
        assert file[2] == "application/json"

    def test_use_long_form_content_type(self, mock_stack, includes):
        """Use custom content type"""

        with tempfile.NamedTemporaryFile(suffix=".json") as tfile:
            request_args = {
                "files": {
                    "file1": {
                        "file_path": tfile.name,
                        "content_type": "abc123",
                        "content_encoding": "def456",
                    }
                }
            }

            file_spec = _get_file_arguments(request_args, mock_stack, includes)

        file = file_spec["files"]["file1"]
        assert file[0] == os.path.basename(tfile.name)
        assert file[2] == "abc123"
        assert file[3] == {"Content-Encoding": "def456"}

    @pytest.mark.parametrize(
        "file_args",
        [
            {
                "file1": {
                    "file_path": "{tmpname}",
                    "content_type": "abc123",
                    "content_encoding": "def456",
                }
            },
            {"file1": "{tmpname}"},
        ],
    )
    def test_format_filename(self, mock_stack, includes, file_args):
        """Filenames should be formatted in short and long styles"""

        with tempfile.NamedTemporaryFile(suffix=".json") as tfile:
            includes.variables["tmpname"] = tfile.name
            request_args = {"files": {"file1": tfile.name}}

            file_spec = _get_file_arguments(request_args, mock_stack, includes)

        file = file_spec["files"]["file1"]
        assert file[0] == os.path.basename(tfile.name)
