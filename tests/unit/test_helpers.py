from mock import patch
import sys
import json
import pytest
import _pytest

from tavern.util import exceptions
from tavern.core import run
from tavern.testutils.helpers import validate_regex, validate_content
from tavern.testutils.pytesthook import YamlItem


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

    def test_normal_args(self):
        with patch("tavern.core.pytest.main") as pmock:
            run(**{
                'tavern_global_cfg': None,
                'in_file': "kfdoskdof",
                'tavern_http_backend': 'requests',
                'tavern_mqtt_backend': 'paho-mqtt',
                'tavern_strict': True,
            })

        assert pmock.called

    def test_extra_args(self):
        with pytest.warns(FutureWarning):
            with patch("tavern.core.pytest.main") as pmock:
                run(**{
                    'tavern_global_cfg': None,
                    'in_file': "kfdoskdof",
                    'tavern_http_backend': 'requests',
                    'tavern_mqtt_backend': 'paho-mqtt',
                    'tavern_strict': True,
                    'gfg': '2efsf',
                })

        assert pmock.called


class TestTavernRepr:

    @pytest.fixture(name="fake_item")
    def fix_fake_item(self, request):
        item = YamlItem(
            name="Fake Test Item",
            parent=request.node,
            spec={},
            path="/tmp/hello",
        )
        return item

    def _make_fake_exc_info(self, exc_type):
        # Copied from pytest tests
        class FakeExcinfo(_pytest._code.ExceptionInfo):
            pass

        try:
            raise exc_type
        except exc_type:
            excinfo = FakeExcinfo(sys.exc_info())

        return excinfo

    def test_not_called_for_normal_exception(self, fake_item):
        """Should call normal pytest repr_info"""
        fake_info = self._make_fake_exc_info(RuntimeError)

        with patch("tavern.testutils.pytesthook.ReprdError") as rmock:
            fake_item.repr_failure(fake_info)

        assert not rmock.called

    def test_not_called_if_flag_not_enabled(self, fake_item):
        """Not called by default for tavern exceptions"""
        fake_info = self._make_fake_exc_info(exceptions.BadSchemaError)

        with patch("tavern.testutils.pytesthook.ReprdError") as rmock:
            fake_item.repr_failure(fake_info)

        assert not rmock.called

    def test_called_for_tavern_exception_ini(self, fake_item):
        """Enable ini flag, should be called"""
        fake_info = self._make_fake_exc_info(exceptions.BadSchemaError)

        with patch.object(fake_item.config, "getini", return_value=True):
            with patch("tavern.testutils.pytesthook.ReprdError") as rmock:
                fake_item.repr_failure(fake_info)

        assert rmock.called

    def test_called_for_tavern_exception_cli(self, fake_item):
        """Enable cli flag, should be called"""
        fake_info = self._make_fake_exc_info(exceptions.BadSchemaError)

        with patch.object(fake_item.config, "getoption", return_value=True):
            with patch("tavern.testutils.pytesthook.ReprdError") as rmock:
                fake_item.repr_failure(fake_info)

        assert rmock.called



@pytest.fixture(name='nested_response')
def fix_nested_response():
    class response_content(object):
        content = {
            "top": {
                "Thing": "value",
                "float": 0.1,
                "nested": {
                    "doubly": {
                        "inner_value": "value",
                        "inner_list": [1, 2, 3],
                    }
                }
            },
            "an_integer": 123,
            "a_string": "abc",
            "a_bool": True
        }

        def json(self):
            return self.content

    return response_content()


class TestContent:
    def test_correct_jmes_path(self, nested_response):
        comparisions = [
            {'jmespath': "top.Thing", 'operator': "eq", 'expected': "value"},
            {'jmespath': "an_integer", 'operator': "eq", 'expected': 123},
            {'jmespath': "top.nested.doubly.inner_list", 'operator': "type", 'expected': "list"},
        ]
        validate_content(nested_response, comparisions)
        assert True

    def test_incorrect_jmes_path(self, nested_response):
        comparisions = [
            {'jmespath': "userId", 'operator': "eq", 'expected': 1}
        ]
        with pytest.raises(exceptions.JMESError):
            validate_content(nested_response, comparisions)

    def test_incorrect_value(self, nested_response):
        comparisions = [
            {'jmespath': "a_bool", 'operator': "eq", 'expected': False}
        ]
        with pytest.raises(exceptions.JMESError):
            validate_content(nested_response, comparisions)
