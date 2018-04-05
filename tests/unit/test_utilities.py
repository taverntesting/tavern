import pytest
import copy

from tavern.schemas.extensions import validate_extensions
from tavern.util import exceptions
from tavern.util.loader import ANYTHING
from tavern.util.dict_util import deep_dict_merge, check_keys_match_recursive


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
