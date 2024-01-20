import pytest

from tavern._core import exceptions
from tavern._core.schema.extensions import (
    validate_grpc_status_is_valid_or_list_of_names as validate_grpc,
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
