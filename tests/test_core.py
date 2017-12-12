import json
from mock import patch, Mock

import pytest
import requests

from tavern.core import run_test
from tavern.util import exceptions


@pytest.fixture(name="fulltest")
def fix_example_test():
    spec = {
        "test_name": "A test with a single stage",
        "stages": [
            {
                "name": "step 1",
                "request": {
                    "url": "http://www.google.com",
                    "method": "GET",
                },
                "response": {
                    "status_code": 200,
                    "body": {
                        "key": "value",
                    },
                    "headers": {
                        "content-type": "application/json",
                    }
                }
            }
        ]
    }

    return spec


@pytest.fixture(name="mockargs")
def fix_mock_response_args(fulltest):
    response = fulltest["stages"][0]["response"]
    content = response["body"]

    args = {
        "spec": requests.Request,
        "content": json.dumps(content).encode("utf8"),
        "status_code": response["status_code"],
        "json": lambda: content,
        "headers": response["headers"],
    }

    return args


class TestRunStages:

    def test_success(self, fulltest, mockargs, includes):
        """Successful test
        """

        mock_response = Mock(**mockargs)

        with patch("tavern.request.requests.Session.request", return_value=mock_response) as pmock:
            run_test("heif", fulltest, includes)

        assert pmock.called

    def test_invalid_code(self, fulltest, mockargs, includes):
        """Wrong status code
        """

        mockargs["status_code"] = 400

        mock_response = Mock(**mockargs)

        with patch("tavern.request.requests.Session.request", return_value=mock_response) as pmock:
            with pytest.raises(exceptions.TestFailError):
                run_test("heif", fulltest, includes)

        assert pmock.called

    def test_invalid_body(self, fulltest, mockargs, includes):
        """Wrong body returned
        """

        mockargs["json"] = lambda: {"wrong": "thing"}

        mock_response = Mock(**mockargs)

        with patch("tavern.request.requests.Session.request", return_value=mock_response) as pmock:
            with pytest.raises(exceptions.TestFailError):
                run_test("heif", fulltest, includes)

        assert pmock.called

    def test_invalid_headers(self, fulltest, mockargs, includes):
        """Wrong headers
        """

        mockargs["headers"] = {"content-type": "application/x-www-url-formencoded"}

        mock_response = Mock(**mockargs)

        with patch("tavern.request.requests.Session.request", return_value=mock_response) as pmock:
            with pytest.raises(exceptions.TestFailError):
                run_test("heif", fulltest, includes)

        assert pmock.called
