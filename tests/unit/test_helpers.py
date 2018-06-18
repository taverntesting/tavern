from mock import patch
import pytest

from tavern.core import run
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


class TestRunAlone:

    def test_run_calls_pytest(self):
        """This should just return from pytest.main()"""

        with patch("tavern.core.pytest.main") as pmock:
            run("abc")

        assert pmock.called

    def test_warngs_cfg(self):
        with pytest.warns(FutureWarning):
            with patch("tavern.core.pytest.main") as pmock:
                run("abc", {"a": "b"})

        assert pmock.called
