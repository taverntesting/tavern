import pytest

from tavern.testutils.helpers import validate_regex


class FakeResponse:
    def __init__(self, text):
        self.text = text
        self.headers = dict(test_header=text)


class TestRegex:

    def test_regex_match(self):
        response = FakeResponse("abchelloabc")

        matched = validate_regex(response, "(?P<greeting>hello)")

        assert "greeting" in matched["regex"]

    def test_regex_no_match(self):
        response = FakeResponse("abchelloabc")

        with pytest.raises(AssertionError):
            validate_regex(response, "(?P<greeting>hola)")

    def test_regex_match_header(self):
        response = FakeResponse("abchelloabc")

        matched = validate_regex(response, "(?P<greeting>hello)", 'test_header')

        assert "greeting" in matched["regex"]

    def test_regex_no_match_header(self):
        response = FakeResponse("abchelloabc")

        with pytest.raises(AssertionError):
            validate_regex(response, "(?P<greeting>hola)", 'test_header')
