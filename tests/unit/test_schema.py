import contextlib
import os
import tempfile
from textwrap import dedent

import pytest
import yaml

from tavern.schemas.files import verify_tests
from tavern.util.exceptions import BadSchemaError
from tavern.util.loader import load_single_document_yaml


@pytest.fixture(name="test_dict")
def fix_test_dict():
    text = dedent(
        """
    ---
    test_name: Make sure server doubles number properly

    stages:
      - name: Make sure number is returned correctly
        request:
          url: http://localhost:5000/double
          json:
            number: 5
          method: POST
          headers:
            content-type: application/json
        response:
          status_code: 200
          json:
            double: 10
    """
    )

    as_dict = yaml.load(text, Loader=yaml.SafeLoader)

    return as_dict


class TestJSON:
    def test_simple_json_body(self, test_dict):
        """Simple json dict in request and response"""
        verify_tests(test_dict)

    def test_json_list_request(self, test_dict):
        """Request contains a list"""
        test_dict["stages"][0]["request"]["json"] = [1, "text", -1]

        verify_tests(test_dict)

    def test_json_list_response(self, test_dict):
        """Response contains a list"""
        test_dict["stages"][0]["response"]["json"] = [1, "text", -1]

        verify_tests(test_dict)


class TestHeaders:
    def test_header_request_list(self, test_dict):
        """Headers must always be a dict"""
        test_dict["stages"][0]["request"]["headers"] = [1, "text", -1]

        with pytest.raises(BadSchemaError):
            verify_tests(test_dict)

    def test_headers_response_list(self, test_dict):
        """Headers must always be a dict"""
        test_dict["stages"][0]["response"]["headers"] = [1, "text", -1]

        with pytest.raises(BadSchemaError):
            verify_tests(test_dict)


class TestParameters:
    def test_header_request_list(self, test_dict):
        """Parameters must always be a dict"""
        test_dict["stages"][0]["request"]["params"] = [1, "text", -1]

        with pytest.raises(BadSchemaError):
            verify_tests(test_dict)


class TestTimeout:
    @pytest.mark.parametrize("incorrect_value", ("abc", True, {"a": 2}, [1, 2, 3]))
    def test_timeout_single_fail(self, test_dict, incorrect_value):
        """Timeout must be a list of floats or a float"""
        test_dict["stages"][0]["request"]["timeout"] = incorrect_value

        with pytest.raises(BadSchemaError):
            verify_tests(test_dict)

    @pytest.mark.parametrize("incorrect_value", ("abc", True, None, {"a": 2}))
    def test_timeout_tuple_fail(self, test_dict, incorrect_value):
        """Timeout must be a list of floats or a float"""
        test_dict["stages"][0]["request"]["timeout"] = [1, incorrect_value]

        with pytest.raises(BadSchemaError):
            verify_tests(test_dict)

        test_dict["stages"][0]["request"]["timeout"] = [incorrect_value, 1]

        with pytest.raises(BadSchemaError):
            verify_tests(test_dict)


class TestCert:
    @pytest.mark.parametrize("correct_value", ("a", ["a", "b"]))
    def test_cert_as_string_tuple_list(self, test_dict, correct_value):
        test_dict["stages"][0]["request"]["cert"] = correct_value
        verify_tests(test_dict)

    @pytest.mark.parametrize(
        "incorrect_value", (None, True, {}, ("a", "b", "c"), [], ["a"], ["a", "b", "c"])
    )
    def test_cert_as_tuple(self, test_dict, incorrect_value):
        test_dict["stages"][0]["request"]["cert"] = incorrect_value
        with pytest.raises(BadSchemaError):
            verify_tests(test_dict)


class TestVerify:
    @pytest.mark.parametrize("correct_value", ("a", True, False))
    def test_verify_with_string_boolean(self, test_dict, correct_value):
        test_dict["stages"][0]["request"]["verify"] = correct_value
        verify_tests(test_dict)

    @pytest.mark.parametrize("incorrect_value", (None, 1, {}, [], ("a", "b")))
    def test_verify_with_incorrect_value(self, test_dict, incorrect_value):
        test_dict["stages"][0]["request"]["verify"] = incorrect_value
        with pytest.raises(BadSchemaError):
            verify_tests(test_dict)


class TestBadSchemaAtCollect:
    """Some errors happen at collection time - harder to test"""

    @staticmethod
    @contextlib.contextmanager
    def wrapfile_nondict(to_wrap):
        with tempfile.NamedTemporaryFile(
            suffix=".yaml", prefix="test_", delete=False
        ) as wrapped_tmp:
            # put into a file
            wrapped_tmp.write(to_wrap.encode("utf8"))
            wrapped_tmp.close()

            try:
                yield wrapped_tmp.name
            finally:
                os.remove(wrapped_tmp.name)

    def test_empty_dict_val(self):
        """Defining an empty mapping value is not allowed"""

        text = dedent(
            """
        ---

        test_name: Test cannot send a set

        stages:
          - name: match top level
            request:
              url: "{host}/fake_dictionary"
              method: GET
              json: {a, b}
            response:
              status_code: 200
              json:
                top: !anything
        """
        )

        with TestBadSchemaAtCollect.wrapfile_nondict(text) as filename:
            with pytest.raises(BadSchemaError):
                load_single_document_yaml(filename)

    def test_empty_list_val(self):
        """Defining an empty list value is not allowed"""

        text = dedent(
            """
        ---

        test_name: Test cannot send a set

        stages:
          - name: match top level
            request:
              url: "{host}/fake_dictionary"
              method: GET
              json:
                - a
                -
                - b
            response:
              status_code: 200
              json:
                top: !anything
        """
        )

        with TestBadSchemaAtCollect.wrapfile_nondict(text) as filename:
            with pytest.raises(BadSchemaError):
                load_single_document_yaml(filename)
