import json
import sys
import tempfile
from textwrap import dedent
from unittest.mock import Mock, patch

import _pytest
import pytest
from tavern.testutils.pytesthook.item import YamlItem
from tavern.util.dict_util import _check_and_format_values, format_keys
from tavern.util.loader import ForceIncludeToken
from tavern.util.strict_util import (
    StrictLevel,
    StrictSetting,
    validate_and_parse_option,
)
import yaml

from tavern._core import exceptions
from tavern._core.dict_util import _check_and_format_values, format_keys
from tavern._core.loader import ForceIncludeToken
from tavern._core.pytest.item import YamlItem
from tavern._core.schema.extensions import validate_file_spec
from tavern._core.strict_util import (
    StrictLevel,
    validate_and_parse_option,
)
from tavern.core import run
from tavern.helpers import (
    validate_content,
    validate_pykwalify,
    validate_regex,
)
from tavern.util import exceptions


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

        with pytest.raises(exceptions.RegexAccessError):
            validate_regex(response, "(?P<greeting>hola)")

    def test_regex_match_header(self):
        response = FakeResponse("abchelloabc")

        matched = validate_regex(response, "(?P<greeting>hello)", header="test_header")

        assert "greeting" in matched["regex"]

    def test_regex_no_match_header(self):
        response = FakeResponse("abchelloabc")

        with pytest.raises(exceptions.RegexAccessError):
            validate_regex(response, "(?P<greeting>hola)", header="test_header")

    @pytest.mark.parametrize(
        "match",
        (
            (r"val(?P<num>\d)", "path1", "val1"),
            (r"val(?P<num>\d)", "path2[0]", "val2"),
            (r"val(?P<num>\d)", "path3.sub", "val3"),
        ),
    )
    def test_in_jmespath(self, match):
        response = FakeResponse(
            json.dumps({"path1": "val1", "path2": ["val2"], "path3": {"sub": "val3"}})
        )

        expression, path, expected = match

        result = validate_regex(response, expression, in_jmespath=path)

        assert result["regex"]["num"] == expected[-1]


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
        with pytest.raises(TypeError):
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

        assert not pmock.called


class TestTavernRepr:
    @pytest.fixture(name="fake_item")
    def fix_fake_item(self, request):
        item = YamlItem.from_parent(
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
        """Does not call tavern repr for non tavern errors"""
        fake_info = self._make_fake_exc_info(RuntimeError)

        with patch("tavern._core.pytesthook.item.ReprdError") as rmock:
            fake_item.repr_failure(fake_info)

        assert not rmock.called

    @pytest.mark.parametrize("ini_flag", [True, False])
    def test_not_called_for_badschema_tavern_exception_(self, fake_item, ini_flag):
        """Does not call taven repr for badschemerror - tavern repr gives no useful information in this case"""
        fake_info = self._make_fake_exc_info(exceptions.BadSchemaError)

        with patch.object(fake_item.config, "getini", return_value=ini_flag):
            with patch("tavern._core.pytesthook.item.ReprdError") as rmock:
                fake_item.repr_failure(fake_info)

        assert not rmock.called

    def test_not_called_ini(self, fake_item):
        """Enable ini flag, should call old style"""
        fake_info = self._make_fake_exc_info(exceptions.InvalidSettingsError)

        with patch.object(fake_item.config, "getini", return_value=True):
            with patch("tavern._core.pytesthook.item.ReprdError") as rmock:
                fake_item.repr_failure(fake_info)

        assert not rmock.called

    def test_not_called_cli(self, fake_item):
        """Enable cli flag, should call old style"""
        fake_info = self._make_fake_exc_info(exceptions.InvalidSettingsError)

        with patch.object(fake_item.config, "getoption", return_value=True):
            with patch("tavern._core.pytesthook.item.ReprdError") as rmock:
                fake_item.repr_failure(fake_info)

        assert not rmock.called


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


@pytest.mark.xfail
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
        with patch("tavern._core.util.dict_util.logger.warning") as wmock:
            _check_and_format_values("{fd}", {"fd": item})

        assert wmock.called_with(
            "Formatting 'fd' will result in it being coerced to a string (it is a {})".format(
                type(item)
            )
        )

    @pytest.mark.parametrize("item", [1, "a", 1.3, format_keys("{s}", dict(s=2))])
    def test_no_warn_good_type(self, item):
        with patch("tavern._core.util.dict_util.logger.warning") as wmock:
            _check_and_format_values("{fd}", {"fd": item})

        assert not wmock.called


class TestFormatWithJson(object):
    @pytest.mark.parametrize(
        "item", [[134], {"a": 2}, yaml, yaml.load, yaml.SafeLoader]
    )
    def test_custom_format(self, item):
        """Can format everything"""
        val = format_keys(ForceIncludeToken("{fd}"), {"fd": item})

        assert val == item

    def test_bad_format_string_extra(self):
        """Extra things in format string"""
        with pytest.raises(exceptions.InvalidFormattedJsonError):
            format_keys(ForceIncludeToken("{fd}gg"), {"fd": "123"})

    def test_bad_format_string_conversion(self):
        """No format string"""
        with pytest.raises(exceptions.InvalidFormattedJsonError):
            format_keys(ForceIncludeToken(""), {"fd": "123"})

    def test_bad_format_string_multiple(self):
        """Multple format spec in string is disallowed"""
        with pytest.raises(exceptions.InvalidFormattedJsonError):
            format_keys(ForceIncludeToken("{a}{b}"), {"fd": "123"})


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


class TestStrictUtils:
    @pytest.mark.parametrize("section", ["json", "headers", "redirect_query_params"])
    @pytest.mark.parametrize("setting", ["on", "off"])
    def test_parse_option(self, section, setting):
        option = "{}:{}".format(section, setting)
        match = validate_and_parse_option(option)

        assert match.section == section

        if setting == "on":
            assert match.is_on()
        else:
            assert not match.is_on()

    @pytest.mark.parametrize("section", ["json", "headers", "redirect_query_params"])
    def test_unset_defaults(self, section):
        match = validate_and_parse_option(section)

        if section == "json":
            assert match.is_on()
        else:
            assert not match.is_on()

    @pytest.mark.parametrize("setting", ["true", "1", "hi", ""])
    def test_fails_bad_setting(self, setting):
        with pytest.raises(exceptions.InvalidConfigurationException):
            validate_and_parse_option("json:{}".format(setting))

    @pytest.mark.parametrize("section", ["json", "headers", "redirect_query_params"])
    def test_defaults(self, section):
        level = StrictLevel([])

        if section == "json":
            assert level.setting_for(section)
        else:
            assert not level.setting_for(section)

    @pytest.mark.parametrize("section", ["true", "1", "hi", ""])
    def test_defaults(self, section):
        level = StrictLevel([])

        with pytest.raises(exceptions.InvalidConfigurationException):
            level.setting_for(section)

    # These tests could be removed, they are testing implementation details...
    @pytest.mark.parametrize("section", ["json", "headers", "redirect_query_params"])
    def test_set_on(self, section):
        level = StrictLevel.from_options([section + ":on"])

        assert level.setting_for(section).setting == StrictSetting.ON
        assert level.setting_for(section).is_on()

    @pytest.mark.parametrize("section", ["json", "headers", "redirect_query_params"])
    def test_set_off(self, section):
        level = StrictLevel.from_options([section + ":off"])

        assert level.setting_for(section).setting == StrictSetting.OFF
        assert not level.setting_for(section).is_on()

    @pytest.mark.parametrize("section", ["json", "headers", "redirect_query_params"])
    def test_unset(self, section):
        level = StrictLevel.from_options([section])

        assert level.setting_for(section).setting == StrictSetting.UNSET
