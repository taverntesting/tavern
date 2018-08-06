from textwrap import dedent
from collections import OrderedDict

import pytest
import yaml
import copy

from tavern.schemas.extensions import validate_extensions
from tavern.util import exceptions
from tavern.util.loader import ANYTHING, IncludeLoader
from tavern.util.dict_util import deep_dict_merge, check_keys_match_recursive, format_keys


class TestValidateFunctions:

    def test_get_extension(self):
        """Loads a validation function correctly

        This doesn't check the signature at the time of writing
        """

        spec = {
            "$ext": {
                "function": "operator:add",
            }
        }

        validate_extensions(spec, None, None)

    def test_get_invalid_module(self):
        """Nonexistent module
        """

        spec = {
            "$ext": {
                "function": "bleuuerhug:add",
            }
        }

        with pytest.raises(exceptions.BadSchemaError):
            validate_extensions(spec, None, None)

    def test_get_nonexistent_function(self):
        """No name in module
        """

        spec = {
            "$ext": {
                "function": "os:aaueurhg",
            }
        }

        with pytest.raises(exceptions.BadSchemaError):
            validate_extensions(spec, None, None)


class TestDictMerge:

    def test_single_level(self):
        """ Merge two depth-one dicts with no conflicts
        """
        dict_1 = {
            'key_1': 'original_value_1',
            'key_2': 'original_value_2'
        }
        dict_2 = {
            'key_2': 'new_value_2',
            'key_3': 'new_value_3'
        }

        result = deep_dict_merge(dict_1, dict_2)

        assert dict_1 == {
            'key_1': 'original_value_1',
            'key_2': 'original_value_2'
        }
        assert dict_2 == {
            'key_2': 'new_value_2',
            'key_3': 'new_value_3'
        }
        assert result == {
            'key_1': 'original_value_1',
            'key_2': 'new_value_2',
            'key_3': 'new_value_3',
        }

    def test_recursive_merge(self):
        """ Merge two depth-one dicts with no conflicts
        """
        dict_1 = {
            'key': {
                'deep_key_1': 'original_value_1',
                'deep_key_2': 'original_value_2'
            }
        }
        dict_2 = {
            'key': {
                'deep_key_2': 'new_value_2',
                'deep_key_3': 'new_value_3'
            }
        }

        result = deep_dict_merge(dict_1, dict_2)

        assert dict_1 == {
            'key': {
                'deep_key_1': 'original_value_1',
                'deep_key_2': 'original_value_2'
            }
        }
        assert dict_2 == {
            'key': {
                'deep_key_2': 'new_value_2',
                'deep_key_3': 'new_value_3'
            }
        }
        assert result == {
            'key': {
                'deep_key_1': 'original_value_1',
                'deep_key_2': 'new_value_2',
                'deep_key_3': 'new_value_3'
            }
        }


class TestMatchRecursive:

    def test_match_dict(self):
        a = {
            "a": [
                {
                    "b": "val",
                },
            ]
        }
        b = copy.deepcopy(a)

        check_keys_match_recursive(a, b, [])

    def test_match_dict_mismatch(self):
        a = {
            "a": [
                {
                    "b": "val",
                },
            ]
        }
        b = copy.deepcopy(a)

        b["a"][0]["b"] = "wrong"

        with pytest.raises(exceptions.KeyMismatchError):
            check_keys_match_recursive(a, b, [])

    def test_match_nested_list(self):
        a = {
            "a": [
                "val"
            ]
        }
        b = copy.deepcopy(a)

        b["a"][0] = "wrong"

        with pytest.raises(exceptions.KeyMismatchError):
            check_keys_match_recursive(a, b, [])

    def test_match_nested_list_length(self):
        a = {
            "a": [
                "val"
            ]
        }
        b = copy.deepcopy(a)

        b["a"].append("wrong")

        with pytest.raises(exceptions.KeyMismatchError):
            check_keys_match_recursive(a, b, [])

    # These ones are testing 'internal' behaviour, might break in future

    def test_match_nested_anything_dict(self):
        a = {
            "a": [
                {
                    "b": ANYTHING,
                },
            ]
        }
        b = copy.deepcopy(a)

        b["a"][0]["b"] = "wrong"

        check_keys_match_recursive(a, b, [])

    def test_match_nested_anything_list(self):
        a = {
            "a": [
                ANYTHING,
            ]
        }
        b = copy.deepcopy(a)

        b["a"][0] = "wrong"

        check_keys_match_recursive(a, b, [])

    def test_match_ordered(self):
        """Should be able to match an ordereddict"""
        first = dict(
            a=1,
            b=2,
        )

        second = OrderedDict(
            b=2,
            a=1,
        )

        check_keys_match_recursive(first, second, [])

    def test_key_case_matters(self):
        """Make sure case of keys matters"""
        a = {
            "a": [
                {
                    "b": "val",
                },
            ]
        }
        b = copy.deepcopy(a)
        b["a"][0] = {"B": "val"}

        with pytest.raises(exceptions.KeyMismatchError):
            check_keys_match_recursive(a, b, [])

    def test_value_case_matters(self):
        """Make sure case of values matters"""
        a = {
            "a": [
                {
                    "b": "val",
                },
            ]
        }
        b = copy.deepcopy(a)
        b["a"][0]["b"] = "VAL"

        with pytest.raises(exceptions.KeyMismatchError):
            check_keys_match_recursive(a, b, [])



@pytest.fixture(name="test_yaml")
def fix_test_yaml():
    text = dedent("""
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
          body:
            double: !float 10
    """)

    return text


class TestCustomTokens:
    def assert_type_value(self, test_value, expected_type, expected_value):
        assert isinstance(test_value, expected_type)
        assert test_value == expected_value

    def test_conversion(self, test_yaml):
        stages = yaml.load(test_yaml, Loader=IncludeLoader)['stages'][0]

        self.assert_type_value(stages['request']['json']['number'], int, 5)
        self.assert_type_value(stages['response']['body']['double'], float, 10.0)
        self.assert_type_value(stages['request']['json']['return_float'], bool, True)
        self.assert_type_value(stages['request']['json']['is_sensitive'], bool, False)
        self.assert_type_value(
            stages['request']['json']['raw_str'],
            str,
            '{{"query": "{{ val1 {{ val2 {{ val3 {{ val4, val5 }} }} }} }}"}}'
        )


class TestFormatKeys:

    def test_format_missing_raises(self):
        to_format = {
            "a": "{b}",
        }

        with pytest.raises(exceptions.MissingFormatError):
            format_keys(to_format, {})

    def test_format_success(self):
        to_format = {
            "a": "{b}",
        }

        final_value = "formatted"

        format_variables = {
            "b": final_value,
        }

        assert format_keys(to_format, format_variables)["a"] == final_value
