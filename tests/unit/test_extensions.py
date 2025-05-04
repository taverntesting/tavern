import pytest

from tavern._core import exceptions
from tavern._core.schema.extensions import (
    validate_grpc_status_is_valid_or_list_of_names as validate_grpc,
    check_parametrize_marks,
)


class TestGrpcCodes:
    @pytest.mark.parametrize("code", ("UNAVAILABLE", "unavailable", "ok", 14, 0))
    def test_validate_grpc_valid_status(self, code):
        assert True is validate_grpc(code, None, None)
        assert True is validate_grpc([code], None, None)

    @pytest.mark.parametrize("code", (-1, "fo", "J", {"status": "OK"}))
    def test_validate_grpc_invalid_status(self, code):
        with pytest.raises(exceptions.BadSchemaError):
            assert False is validate_grpc(code, None, None)

        with pytest.raises(exceptions.BadSchemaError):
            assert False is validate_grpc([code], None, None)


class TestParametrizeMarks:
    @pytest.mark.parametrize(
        "parametrize_spec",
        [
            # Valid string key
            {"key": "a", "vals": [1, 2, 3]},
            # Valid list key with matching vals
            {"key": ["a", "b"], "vals": [[1, 2], [3, 4]]},
            # Valid ext function for vals
            {"key": "a", "vals": {"$ext": {"function": "helpers:return_list_vals"}}},
            {"key": ["a", "b"], "vals": {"$ext": {"function": "helpers:return_nested_vals"}}},
        ],
    )
    def test_valid_parametrize_marks(self, parametrize_spec):
        """Should validate correct parametrize mark configurations"""
        assert check_parametrize_marks(parametrize_spec, None, None) is True

    @pytest.mark.parametrize(
        "parametrize_spec,err_msg",
        [
            # Invalid key type
            (
                {"key": {"a": "b"}, "vals": []},
                "'key' must be a string or a list"
            ),
            # Vals not list or ext function
            (
                {"key": "a", "vals": "invalid"},
                "'vals' should be a list"
            ),
            # List key with non-list vals
            (
                {"key": ["a", "b"], "vals": [1, 2]},
                "If 'key' is a list, 'vals' must be a list of lists"
            ),
            # List key with mismatched lengths
            (
                {"key": ["a", "b"], "vals": [[1], [2]]},
                "If 'key' is a list, 'vals' must be a list of lists where each list is the same length as 'key'"
            ),
            # List key with invalid val items
            (
                {"key": ["a", "b"], "vals": [[1, 2], "invalid"]},
                "If 'key' is a list, 'vals' must be a list of lists"
            ),
        ],
    )
    def test_invalid_parametrize_marks(self, parametrize_spec, err_msg):
        """Should reject invalid parametrize mark configurations"""
        with pytest.raises(exceptions.BadSchemaError) as excinfo:
            check_parametrize_marks(parametrize_spec, None, None)

        assert err_msg in str(excinfo.value)
