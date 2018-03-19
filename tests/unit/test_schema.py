from textwrap import dedent

import pytest
import yaml

from tavern.util.exceptions import BadSchemaError
from tavern.schemas.files import verify_tests


@pytest.fixture(name="test_dict")
def fix_test_dict():
    text = dedent("""
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
          body:
            double: 10
    """)

    as_dict = yaml.load(text)

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
        test_dict["stages"][0]["response"]["body"] = [1, "text", -1]

        verify_tests(test_dict)

    def test_json_value_request(self, test_dict):
        """Don't match other stuff"""
        test_dict["stages"][0]["request"]["json"] = "Hello"

        with pytest.raises(BadSchemaError):
            verify_tests(test_dict)

    def test_json_value_response(self, test_dict):
        """Don't match other stuff"""
        test_dict["stages"][0]["response"]["body"] = "Hi"

        with pytest.raises(BadSchemaError):
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
