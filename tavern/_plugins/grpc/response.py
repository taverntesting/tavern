import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Optional, TypedDict, Union

import grpc
import proto.message
from google.protobuf import json_format
from grpc import StatusCode

from tavern._core import exceptions
from tavern._core.dict_util import check_expected_keys
from tavern._core.exceptions import TestFailError
from tavern._core.pytest.config import TestConfig
from tavern._core.schema.extensions import to_grpc_status
from tavern._plugins.grpc.client import GRPCClient
from tavern.response import BaseResponse

if TYPE_CHECKING:
    from tavern._plugins.grpc.request import WrappedFuture

logger: logging.Logger = logging.getLogger(__name__)


GRPCCode = Union[str, int, list[str], list[int]]


def _to_grpc_name(status: GRPCCode) -> Union[str, list[str]]:
    if isinstance(status, list):
        return [_to_grpc_name(s) for s in status]  # type:ignore

    if status_name := to_grpc_status(status):
        return status_name.upper()

    # This should have been verified before this
    raise exceptions.GRPCServiceException(f"unknown status code '{status}'")


class _GRPCExpected(TypedDict):
    """What the 'expected' block for a grpc response should contain"""

    status: GRPCCode
    details: Any
    body: Mapping


class GRPCResponse(BaseResponse):
    def __init__(
        self,
        client: GRPCClient,
        name: str,
        expected: Union[_GRPCExpected, Mapping],
        test_block_config: TestConfig,
    ) -> None:
        check_expected_keys({"body", "status", "details", "save"}, expected)
        super().__init__(name, expected, test_block_config)

        self._client = client

    def __str__(self):
        if self.response:
            return self.response.payload
        else:
            return "<Not run yet>"

    def _validate_block(self, blockname: str, block: Mapping) -> None:
        """Validate a block of the response

        Args:
            blockname: which part of the response is being checked
            block: The actual part being checked
        """
        try:
            expected_block = self.expected["body"] or {}
        except KeyError:
            expected_block = {}

        if isinstance(expected_block, dict):
            if expected_block.pop("$ext", None):
                logger.warning(
                    "$ext function found in block %s - this has been moved to verify_response_with block - see documentation",
                    blockname,
                )

        logger.debug("Validating response %s against %s", blockname, expected_block)

        test_strictness = self.test_block_config.strict
        block_strictness = test_strictness.option_for(blockname)
        self.recurse_check_key_match(expected_block, block, blockname, block_strictness)

    def verify(self, response: "WrappedFuture") -> Mapping:
        grpc_response = response.response

        logger.debug(f"grpc status code: {grpc_response.code()}")
        logger.debug(f"grpc details: {grpc_response.details()}")

        verify_status = [StatusCode.OK.name]
        if status := self.expected.get("status", None):
            verify_status = _to_grpc_name(status)  # type: ignore
            if not isinstance(verify_status, list):
                verify_status = [verify_status]

        if grpc_response.code().name not in verify_status:
            self._adderr(
                "expected status %s, but the actual response '%s'",
                verify_status,
                grpc_response.code().name,
            )

        if "details" in self.expected:
            verify_details = self.expected["details"]
            if verify_details != grpc_response.details():
                self._adderr(
                    "expected details '%s', but the actual response '%s'",
                    verify_details,
                    grpc_response.details(),
                )

        saved = self._handle_grpc_response(grpc_response, response, verify_status) or {}

        if self.errors:
            raise TestFailError(
                f"Test '{self.name:s}' failed:\n{self._str_errors():s}",
                failures=self.errors,
            )

        return saved

    def _handle_grpc_response(
        self,
        grpc_response: Union[grpc.Call, grpc.Future],
        response: "WrappedFuture",
        verify_status: list[str],
    ) -> Optional[dict[str, Any]]:
        if grpc_response.code().name != "OK":
            # TODO: Should allow checking grpc RPC error details etc.
            logger.info(
                f"skipping body checking due to {grpc_response.code()} response"
            )
            return None

        if "body" in self.expected and verify_status != ["OK"]:
            self._adderr(
                "'body' was specified in response, but expected status code was not 'OK'"
            )
            return None

        _, output_type = self._client.get_method_types(response.service_name)
        result: proto.message.Message = grpc_response.result()

        if not isinstance(result, output_type):
            # Note: This is probably unexpected in some cases
            self._adderr(
                f"response from server ({type(response)}) was not the same type as expected from the registered definition ({output_type})"
            )
            return None

        json_result = json_format.MessageToDict(
            result,
            including_default_value_fields=True,
            preserving_proto_field_name=True,
        )

        if "body" in self.expected:
            expected_parsed = output_type()
            try:
                json_format.ParseDict(self.expected["body"], expected_parsed)
            except json_format.ParseError as e:
                self._adderr(f"response body was not in the right format: {e}", e=e)

            self._validate_block("json", json_result)
            self._maybe_run_validate_functions(json_result)

        saved: dict[str, Any] = {}
        saved.update(self.maybe_get_save_values_from_save_block("body", json_result))
        saved.update(self.maybe_get_save_values_from_ext(json_result, self.expected))

        return saved
