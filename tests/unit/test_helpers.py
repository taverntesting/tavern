import sys
import tempfile
from textwrap import dedent

import _pytest
import pytest
import yaml
from mock import Mock
from mock import patch

from tavern.core import run
from tavern.schemas.extensions import validate_file_spec
from tavern.testutils.helpers import validate_pykwalify
from tavern.testutils.helpers import validate_regex, validate_content
from tavern.testutils.pytesthook.item import YamlItem
from tavern.util import exceptions
from tavern.util.dict_util import _check_parsed_values, format_keys


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

        matched = validate_regex(response, "(?P<greeting>hello)", "test_header")

        assert "greeting" in matched["regex"]

    def test_regex_no_match_header(self):
        response = FakeResponse("abchelloabc")

        with pytest.raises(AssertionError):
            validate_regex(response, "(?P<greeting>hola)", "test_header")


class TestRunAlone:
    def test_run_calls_pytest(self):
        """This should just return from pytest.main()"""

        with patch("tavern.core.pytest.main") as pmock:
            run("abc")

        assert pmock.called

    def test_normal_args(self):
        with patch("tavern.core.pytest.main") as pmock:
            run(
                **{
                    "tavern_global_cfg": None,
                    "in_file": "kfdoskdof",
                    "tavern_http_backend": "requests",
                    "tavern_mqtt_backend": "paho-mqtt",
                    "tavern_strict": True,
                }
            )

        assert pmock.called

    def test_extra_args(self):
        with pytest.warns(FutureWarning):
            with patch("tavern.core.pytest.main") as pmock:
                run(
                    **{
                        "tavern_global_cfg": None,
                        "in_file": "kfdoskdof",
                        "tavern_http_backend": "requests",
                        "tavern_mqtt_backend": "paho-mqtt",
                        "tavern_strict": True,
                        "gfg": "2efsf",
                    }
                )

        assert pmock.called


class TestTavernRepr:
    @pytest.fixture(name="fake_item")
    def fix_fake_item(self, request):
        item = YamlItem(
            name="Fake Test Item", parent=request.node, spec={}, path="/tmp/hello"
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

        with patch("tavern.testutils.pytesthook.item.ReprdError") as rmock:
            fake_item.repr_failure(fake_info)

        assert not rmock.called

    def test_not_called_if_flag_not_enabled(self, fake_item):
        """Not called by default for tavern exceptions"""
        fake_info = self._make_fake_exc_info(exceptions.BadSchemaError)

        with patch("tavern.testutils.pytesthook.item.ReprdError") as rmock:
            fake_item.repr_failure(fake_info)

        assert not rmock.called

    def test_not_called_for_badschema_tavern_exception_(self, fake_item):
        """Enable ini flag, should be called"""
        fake_info = self._make_fake_exc_info(exceptions.BadSchemaError)

        with patch.object(fake_item.config, "getini", return_value=True):
            with patch("tavern.testutils.pytesthook.item.ReprdError") as rmock:
                fake_item.repr_failure(fake_info)

        assert not rmock.called

    def test_called_for_tavern_exception_ini(self, fake_item):
        """Enable ini flag, should be called"""
        fake_info = self._make_fake_exc_info(exceptions.InvalidSettingsError)

        with patch.object(fake_item.config, "getini", return_value=True):
            with patch("tavern.testutils.pytesthook.item.ReprdError") as rmock:
                fake_item.repr_failure(fake_info)

        assert rmock.called

    def test_called_for_tavern_exception_cli(self, fake_item):
        """Enable cli flag, should be called"""
        fake_info = self._make_fake_exc_info(exceptions.InvalidSettingsError)

        with patch.object(fake_item.config, "getoption", return_value=True):
            with patch("tavern.testutils.pytesthook.item.ReprdError") as rmock:
                fake_item.repr_failure(fake_info)

        assert rmock.called


@pytest.fixture(name="nested_response")
def fix_nested_response():
    class response_content(object):
        content = {
            "top": {
                "Thing": "value",
                "float": 0.1,
                "nested": {"doubly": {"inner_value": "value", "inner_list": [1, 2, 3]}},
            },
            "an_integer": 123,
            "a_string": "abc",
            "a_bool": True,
        }

        def json(self):
            return self.content

    return response_content()


class TestContent:
    def test_correct_jmes_path(self, nested_response):
        comparisons = [
            {"jmespath": "top.Thing", "operator": "eq", "expected": "value"},
            {"jmespath": "an_integer", "operator": "eq", "expected": 123},
            {
                "jmespath": "top.nested.doubly.inner_list",
                "operator": "type",
                "expected": "list",
            },
        ]
        validate_content(nested_response, comparisons)
        assert True

    def test_incorrect_jmes_path(self, nested_response):
        comparisons = [{"jmespath": "userId", "operator": "eq", "expected": 1}]
        with pytest.raises(exceptions.JMESError):
            validate_content(nested_response, comparisons)

    def test_incorrect_value(self, nested_response):
        comparisons = [{"jmespath": "a_bool", "operator": "eq", "expected": False}]
        with pytest.raises(exceptions.JMESError):
            validate_content(nested_response, comparisons)


class TestPykwalifyExtension:
    def test_validate_schema_correct(self, nested_response):
        correct_schema = dedent(
            """
              type: map
              required: true
              mapping:
                top:
                  type: map
                  required: true
                  mapping:
                    Thing:
                      type: str
                    float:
                      type: float
                    nested:
                      type: any
                an_integer:
                  type: int
                a_string:
                  type: str
                a_bool:
                  type: bool
        """
        )

        validate_pykwalify(
            nested_response, yaml.load(correct_schema, Loader=yaml.SafeLoader)
        )

    def test_validate_schema_incorrect(self, nested_response):
        correct_schema = dedent(
            """
              type: seq
              required: true
              sequence:
                - type: str
        """
        )

        with pytest.raises(exceptions.BadSchemaError):
            validate_pykwalify(
                nested_response, yaml.load(correct_schema, Loader=yaml.SafeLoader)
            )


class TestCheckParseValues(object):
    @pytest.mark.parametrize(
        "item", [[134], {"a": 2}, yaml, yaml.load, yaml.SafeLoader]
    )
    def test_warns_bad_type(self, item):
        with patch("tavern.util.dict_util.logger.warning") as wmock:
            _check_parsed_values("{fd}", {"fd": item})

        assert wmock.called_with(
            "Formatting 'fd' will result in it being coerced to a string (it is a {})".format(
                type(item)
            )
        )

    @pytest.mark.parametrize("item", [1, "a", 1.3, format_keys("{s}", dict(s=2))])
    def test_no_warn_good_type(self, item):
        with patch("tavern.util.dict_util.logger.warning") as wmock:
            _check_parsed_values("{fd}", {"fd": item})

        assert not wmock.called


class TestCheckFileSpec(object):
    def _wrap_test_block(self, dowith):
        validate_file_spec({"files": dowith}, Mock(), Mock())

    def test_string_valid(self):
        with tempfile.NamedTemporaryFile() as tfile:
            self._wrap_test_block(tfile.name)

    def test_dict_valid(self):
        with tempfile.NamedTemporaryFile() as tfile:
            self._wrap_test_block({"file_path": tfile.name})

    def test_nonexistsnt_string(self):
        with pytest.raises(exceptions.BadSchemaError):
            self._wrap_test_block("kdsfofs")

    def nonexistent_dict(self):
        with pytest.raises(exceptions.BadSchemaError):
            self._wrap_test_block({"file_path": "gogfgl"})

    def extra_keys_dict(self):
        with pytest.raises(exceptions.BadSchemaError):
            self._wrap_test_block({"file_path": "gogfgl", "blop": 123})
