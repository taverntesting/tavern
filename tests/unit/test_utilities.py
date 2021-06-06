from collections import OrderedDict
import contextlib
import copy
import os
import tempfile
from textwrap import dedent
from unittest.mock import Mock, patch

import pytest
import yaml

from tavern._core import exceptions
from tavern._core.dict_util import (
    check_keys_match_recursive,
    deep_dict_merge,
    format_keys,
    recurse_access_key,
)
from tavern._core.loader import (
    ANYTHING,
    DictSentinel,
    FloatSentinel,
    IncludeLoader,
    IntSentinel,
    ListSentinel,
    StrSentinel,
    construct_include,
    load_single_document_yaml,
)
from tavern._core.schema.extensions import validate_extensions
from tavern._core.schema.files import wrapfile


class TestValidateFunctions:
    def test_get_extension(self):
        """Loads a validation function correctly

        This doesn't check the signature at the time of writing
        """

        spec = {"function": "operator:add"}

        validate_extensions(spec, None, None)

    def test_get_extension_list(self):
        """Loads a validation function correctly

        This doesn't check the signature at the time of writing
        """

        spec = [{"function": "operator:add"}]

        validate_extensions(spec, None, None)

    def test_get_extension_list_empty(self):
        """Loads a validation function correctly

        This doesn't check the signature at the time of writing
        """

        spec = []

        validate_extensions(spec, None, None)

    def test_get_invalid_module(self):
        """Nonexistent module"""

        spec = {"function": "bleuuerhug:add"}

        with pytest.raises(exceptions.BadSchemaError):
            validate_extensions(spec, None, None)

    def test_get_nonexistent_function(self):
        """No name in module"""

        spec = {"function": "os:aaueurhg"}

        with pytest.raises(exceptions.BadSchemaError):
            validate_extensions(spec, None, None)


class TestDictMerge:
    def test_single_level(self):
        """Merge two depth-one dicts with no conflicts"""
        dict_1 = {"key_1": "original_value_1", "key_2": "original_value_2"}
        dict_2 = {"key_2": "new_value_2", "key_3": "new_value_3"}

        result = deep_dict_merge(dict_1, dict_2)

        assert dict_1 == {"key_1": "original_value_1", "key_2": "original_value_2"}
        assert dict_2 == {"key_2": "new_value_2", "key_3": "new_value_3"}
        assert result == {
            "key_1": "original_value_1",
            "key_2": "new_value_2",
            "key_3": "new_value_3",
        }

    def test_recursive_merge(self):
        """Merge two depth-one dicts with no conflicts"""
        dict_1 = {
            "key": {"deep_key_1": "original_value_1", "deep_key_2": "original_value_2"}
        }
        dict_2 = {"key": {"deep_key_2": "new_value_2", "deep_key_3": "new_value_3"}}

        result = deep_dict_merge(dict_1, dict_2)

        assert dict_1 == {
            "key": {"deep_key_1": "original_value_1", "deep_key_2": "original_value_2"}
        }
        assert dict_2 == {
            "key": {"deep_key_2": "new_value_2", "deep_key_3": "new_value_3"}
        }
        assert result == {
            "key": {
                "deep_key_1": "original_value_1",
                "deep_key_2": "new_value_2",
                "deep_key_3": "new_value_3",
            }
        }


class TestMatchRecursive:
    def test_match_dict(self):
        a = {"a": [{"b": "val"}]}
        b = copy.deepcopy(a)

        check_keys_match_recursive(a, b, [])

    def test_match_dict_mismatch(self):
        a = {"a": [{"b": "val"}]}
        b = copy.deepcopy(a)

        b["a"][0]["b"] = "wrong"

        with pytest.raises(exceptions.KeyMismatchError):
            check_keys_match_recursive(a, b, [])

    def test_match_nested_list(self):
        a = {"a": ["val"]}
        b = copy.deepcopy(a)

        b["a"][0] = "wrong"

        with pytest.raises(exceptions.KeyMismatchError):
            check_keys_match_recursive(a, b, [])

    def test_match_nested_list_length(self):
        a = {"a": ["val"]}
        b = copy.deepcopy(a)

        b["a"].append("wrong")

        with pytest.raises(exceptions.KeyMismatchError):
            check_keys_match_recursive(a, b, [])

    # These ones are testing 'internal' behaviour, might break in future

    def test_match_nested_anything_dict(self):
        a = {"a": [{"b": ANYTHING}]}
        b = copy.deepcopy(a)

        b["a"][0]["b"] = "wrong"

        check_keys_match_recursive(a, b, [])

    def test_match_nested_anything_list(self):
        a = {"a": [ANYTHING]}
        b = copy.deepcopy(a)

        b["a"][0] = "wrong"

        check_keys_match_recursive(a, b, [])

    def test_match_ordered(self):
        """Should be able to match an ordereddict"""
        first = dict(a=1, b=2)

        second = OrderedDict(b=2, a=1)

        check_keys_match_recursive(first, second, [])

    def test_key_case_matters(self):
        """Make sure case of keys matters"""
        a = {"a": [{"b": "val"}]}
        b = copy.deepcopy(a)
        b["a"][0] = {"B": "val"}

        with pytest.raises(exceptions.KeyMismatchError):
            check_keys_match_recursive(a, b, [])

    def test_value_case_matters(self):
        """Make sure case of values matters"""
        a = {"a": [{"b": "val"}]}
        b = copy.deepcopy(a)
        b["a"][0]["b"] = "VAL"

        with pytest.raises(exceptions.KeyMismatchError):
            check_keys_match_recursive(a, b, [])

    @pytest.mark.parametrize(
        "token, response",
        [
            (IntSentinel(), 2),
            (ListSentinel(), [1, 2, 3]),
            (DictSentinel(), {2: 2}),
            (FloatSentinel(), 4.5),
            (StrSentinel(), "dood"),
        ],
    )
    def test_type_token_matches(self, token, response):
        """Make sure type tokens match with generic types"""
        check_keys_match_recursive(token, response, [])

    @pytest.mark.parametrize(
        "token, response",
        [
            (IntSentinel(), 2.3),
            (ListSentinel(), 1),
            (DictSentinel(), [4, 5, 6]),
            (FloatSentinel(), "4"),
            (StrSentinel(), {"a": 2}),
        ],
    )
    def test_type_token_no_match_errors(self, token, response):
        """Make sure type tokens do not match if the type is wrong"""
        with pytest.raises(exceptions.KeyMismatchError):
            check_keys_match_recursive(token, response, [])


class TestNonStrictListMatching:
    def test_match_list_items(self):
        """Should match any 2 list items if strict is False, not if it's True"""
        a = ["b"]
        b = ["a", "b", "c"]

        with pytest.raises(exceptions.KeyMismatchError):
            check_keys_match_recursive(a, b, [])

        check_keys_match_recursive(a, b, [], strict=False)

    def test_match_multiple(self):
        """As long as they are in the right order, it can match multiple
        items"""
        a = ["a", "c"]
        b = ["a", "b", "c"]

        with pytest.raises(exceptions.KeyMismatchError):
            check_keys_match_recursive(a, b, [])

        check_keys_match_recursive(a, b, [], strict=False)

    def test_match_multiple_wrong_order(self):
        """Raises an error if the expected items are in the wrong order"""
        a = ["c", "a"]
        b = ["a", "b", "c"]

        with pytest.raises(exceptions.KeyMismatchError):
            check_keys_match_recursive(a, b, [])

        with pytest.raises(exceptions.KeyMismatchError):
            check_keys_match_recursive(a, b, [], strict=False)

    def test_match_wrong_type(self):
        """Can't match incorrect type"""
        a = [1]
        b = ["1", "2", "3"]

        with pytest.raises(exceptions.KeyMismatchError):
            check_keys_match_recursive(a, b, [])

        with pytest.raises(exceptions.KeyMismatchError):
            check_keys_match_recursive(a, b, [], strict=False)

    def test_match_list_items_more_as(self):
        """One of them is present, the others aren't"""
        a = ["a", "b", "c"]
        b = ["a"]

        with pytest.raises(exceptions.KeyMismatchError):
            check_keys_match_recursive(a, b, [])

        with pytest.raises(exceptions.KeyMismatchError):
            check_keys_match_recursive(a, b, [], strict=False)


@pytest.fixture(name="test_yaml")
def fix_test_yaml():
    text = dedent(
        """
    ---
    test_name: Make sure server doubles number properly

    stages:
      - name: Make sure number is returned correctly
        request:
          url: http://localhost:5000/double
          json:
            is_sensitive: !bool "False"
            raw_str: !raw '{"query": "{ val1 { val2 { val3 { val4, val5 } } } }"}'
            number: !int '5'
            return_float: !bool "True"
          method: POST
          headers:
            content-type: application/json
        response:
          status_code: 200
          json:
            double: !float 10
    """
    )

    return text


class TestCustomTokens:
    def assert_type_value(self, test_value, expected_type, expected_value):
        assert isinstance(test_value, expected_type)
        assert test_value == expected_value

    def test_conversion(self, test_yaml):
        stages = yaml.load(test_yaml, Loader=IncludeLoader)["stages"][0]

        self.assert_type_value(stages["request"]["json"]["number"], int, 5)
        self.assert_type_value(stages["response"]["json"]["double"], float, 10.0)
        self.assert_type_value(stages["request"]["json"]["return_float"], bool, True)
        self.assert_type_value(stages["request"]["json"]["is_sensitive"], bool, False)
        self.assert_type_value(
            stages["request"]["json"]["raw_str"],
            str,
            '{{"query": "{{ val1 {{ val2 {{ val3 {{ val4, val5 }} }} }} }}"}}',
        )


class TestFormatKeys:
    def test_format_missing_raises(self):
        to_format = {"a": "{b}"}

        with pytest.raises(exceptions.MissingFormatError):
            format_keys(to_format, {})

    def test_format_success(self):
        to_format = {"a": "{b}"}

        final_value = "formatted"

        format_variables = {"b": final_value}

        assert format_keys(to_format, format_variables)["a"] == final_value

    def test_no_double_format_failure(self):
        to_format = "{{b}}"

        final_value = "{b}"

        format_variables = {"b": final_value}

        formatted = format_keys(to_format, format_variables)
        assert formatted == final_value
        formatted_2 = format_keys(formatted, {})
        assert formatted_2 == final_value


class TestRecurseAccess:
    @pytest.fixture
    def nested_data(self):
        data = {"a": ["b", {"c": "d"}]}

        return data

    @pytest.mark.parametrize(
        "old_query, new_query, expected_data",
        (("a.0", "a[0]", "b"), ("a.1.c", "a[1].c", "d")),
    )
    def test_search_old_style(self, nested_data, old_query, new_query, expected_data):
        """Make sure old style searches perform the same as jmes queries"""

        with pytest.raises(exceptions.JMESError):
            recurse_access_key(nested_data, old_query)

        new_val = recurse_access_key(nested_data, new_query)
        assert new_val == expected_data

    @pytest.mark.parametrize("new_query", ("f", "a[3]", "a[1].x"))
    def test_missing_search(self, nested_data, new_query):
        """Searching for data not in given data returns None, because of the way the jmespath library works..."""

        assert recurse_access_key(nested_data, new_query) is None


class TestLoadCfg:
    def test_load_one(self):
        example = {"a": "b"}

        with wrapfile(example) as f:
            assert example == load_single_document_yaml(f)

    def test_load_multiple_fails(self):
        example = [{"a": "b"}, {"c": "d"}]

        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as wrapped_tmp:
            # put into a file
            dumped = yaml.dump_all(example)
            wrapped_tmp.write(dumped.encode("utf8"))
            wrapped_tmp.close()

            try:
                with pytest.raises(exceptions.UnexpectedDocumentsError):
                    load_single_document_yaml(wrapped_tmp.name)
            finally:
                os.remove(wrapped_tmp.name)

    @pytest.mark.parametrize("value", ("b", "三木"))
    def test_load_utf8(self, value):
        """if yaml has utf8 char , may load error"""
        content = f"""a: {value}""" ""

        with tempfile.NamedTemporaryFile(suffix=".yaml", delete=False) as f:
            f.write(content.encode("utf8"))

        try:
            load_single_document_yaml(f.name)

        finally:
            os.remove(f.name)


class TestLoadFile:
    @staticmethod
    @contextlib.contextmanager
    def magic_wrap(to_wrap, suffix):
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as wrapped_tmp:
            dumped = yaml.dump(to_wrap, default_flow_style=False)
            wrapped_tmp.write(dumped.encode("utf8"))
            wrapped_tmp.close()

            try:
                yield wrapped_tmp.name
            finally:
                os.remove(wrapped_tmp.name)

    @pytest.mark.parametrize("suffix", (".yaml", ".yml", ".json"))
    def test_load_extensions(self, suffix):
        example = {"a": "b"}

        with TestLoadFile.magic_wrap(example, suffix) as tmpfile:
            with patch("tavern._core.util.loader.os.path.join", return_value=tmpfile):
                assert example == construct_include(Mock(), Mock())

    def test_load_bad_extension(self):
        example = {"a": "b"}

        with TestLoadFile.magic_wrap(example, ".bllakjf") as tmpfile:
            with patch("tavern._core.util.loader.os.path.join", return_value=tmpfile):
                with pytest.raises(exceptions.BadSchemaError):
                    construct_include(Mock(), Mock())

    def test_include_path(self):
        example = {"a": "b"}

        with TestLoadFile.magic_wrap(example, ".yaml") as tmpfile:
            tmppath, tmpfilename = os.path.split(tmpfile)
            with pytest.raises(exceptions.BadSchemaError):
                construct_include(
                    Mock(
                        _root="/does-not-exist", construct_scalar=lambda x: tmpfilename
                    ),
                    Mock(),
                )

            with patch("tavern._core.util.loader.IncludeLoader.env_path_list", None):
                assert example == construct_include(
                    Mock(_root=tmppath, construct_scalar=lambda x: tmpfilename), Mock()
                )

            os.environ[IncludeLoader.env_var_name] = tmppath
            with patch("tavern._core.util.loader.IncludeLoader.env_path_list", None):
                assert example == construct_include(
                    Mock(
                        _root="/does-not-exist", construct_scalar=lambda x: tmpfilename
                    ),
                    Mock(),
                )
