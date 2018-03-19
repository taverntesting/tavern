import pytest

from tavern.schemas.extensions import validate_extensions
from tavern.util import exceptions
from tavern.util.dict_util import deep_dict_merge


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
