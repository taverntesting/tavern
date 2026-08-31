import logging
from collections.abc import Mapping
from typing import TYPE_CHECKING, Any, Optional, TypedDict, Union

import grpc
import proto.message
from google.protobuf import json_format

# Imported for the side effect of registering the standard google.rpc error details (BadRequest,
# ErrorInfo, etc.) in the descriptor pool, so they can be unpacked from a response
from google.rpc import error_details_pb2  # noqa: F401
from grpc_status import rpc_status

from tavern._core import exceptions
from tavern._core.dict_util import check_expected_keys, check_keys_match_recursive
from tavern._core.exceptions import TestFailError
from tavern._core.loader import ANYTHING
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
    error_message: Any
    details: Any
    body: Mapping


class GRPCResponse(BaseResponse):
    def __init__(
        self,
        client: GRPCClient,
        name: str,
        expected: _GRPCExpected | Mapping,
        test_block_config: TestConfig,
    ) -> None:
        check_expected_keys(
            {"body", "status", "error_message", "details", "save"}, expected
        )
        super().__init__(
            name,
            expected,
            test_block_config,
        )

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

    def _verify_error_message(self, grpc_response: grpc.Call | grpc.Future) -> None:
        """Check the expected error message against the 'details' string of the response

        This is the string passed to set_details/abort on the server - not to be confused with
        the 'details' of the response block, which are the messages in the google.rpc.Status.
        """
        self._check_match(
            self.expected["error_message"],
            grpc_response.details() or "",
            "error_message",
        )

    def _verify_details(self, grpc_response: grpc.Call | grpc.Future) -> None:
        """Check the expected error details against the ones attached to the response"""
        expected_details = self.expected["details"]

        actual_details = self._get_rich_details(grpc_response)

        if actual_details is None and expected_details is not ANYTHING:
            self._adderr(
                "expected error details '%s' in the response, but there were none",
                expected_details,
            )
            return

        self._check_match(expected_details, actual_details, "details")

    def _check_match(self, expected: Any, actual: Any, blockname: str) -> None:
        """Compare part of the response, adding an error if it does not match

        Going through the normal matching rather than just comparing the values means type
        sentinels like !re_search or !anything can be used.
        """
        try:
            check_keys_match_recursive(
                expected,
                actual,
                [blockname],
                self.test_block_config.strict.option_for("json"),
            )
        except exceptions.KeyMismatchError as e:
            self._adderr(e.args[0], e=e)

    def _get_rich_details(
        self, grpc_response: grpc.Call | grpc.Future
    ) -> list[Any] | None:
        """Get the rich error details attached to the response, as json

        These are the messages (google.rpc.BadRequest, google.rpc.ErrorInfo, etc.) packed into
        the google.rpc.Status which the server put into the 'grpc-status-details-bin' trailing
        metadata, as described in https://grpc.io/docs/guides/error/. Each one is converted to a
        dict including the '@type' key identifying it.
        """
        try:
            status = rpc_status.from_call(grpc_response)  # type:ignore[arg-type]
        except ValueError as e:
            self._adderr(
                "response contained rich error details, but they did not match the status of the response itself",
                e=e,
            )
            return None

        if status is None:
            logger.debug("no rich error details on response")
            return None

        try:
            # Unlike the response body, fields which were not set are left out - the details are
            # a bag of arbitrary messages, so making the user spell out every unset field of
            # every one of them would be unusable with strict key checking turned on
            as_dict = json_format.MessageToDict(
                status,
                preserving_proto_field_name=True,
            )
        except (json_format.Error, TypeError) as e:
            # Happens if one of the packed messages is not in the descriptor pool, ie the proto
            # defining it was never loaded
            self._adderr("unable to parse rich error details from response: %s", e, e=e)
            return None

        return as_dict.get("details", [])

    def verify(self, response: "WrappedFuture") -> Mapping:
        grpc_response = response.response

        logger.debug(f"grpc status code: {grpc_response.code()}")
        logger.debug(f"grpc details: {grpc_response.details()}")

        verify_status = [grpc.StatusCode.OK.name]
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

        if "error_message" in self.expected:
            self._verify_error_message(grpc_response)

        if "details" in self.expected:
            self._verify_details(grpc_response)

        saved = self._handle_grpc_response(grpc_response, response, verify_status) or {}

        if self.errors:
            raise TestFailError(
                f"Test '{self.name:s}' failed:\n{self._str_errors():s}",
                failures=self.errors,
            )

        return saved

    def _handle_grpc_response(
        self,
        grpc_response: grpc.Call | grpc.Future,
        response: "WrappedFuture",
        verify_status: list[str],
    ) -> Optional[dict[str, Any]]:
        if "body" in self.expected and verify_status != ["OK"]:
            self._adderr(
                "'body' was specified in response, but expected status code was not 'OK'"
            )
            return None

        _, output_type = self._client.get_method_types(response.service_name)

        try:
            result: proto.message.Message = grpc_response.result()
        except grpc.RpcError as e:
            # A non-OK response has no message attached to it, so there is
            # nothing to check an expected body against
            # TODO: Should allow checking grpc RPC error details etc.
            if "body" in self.expected:
                self._adderr(
                    "expected a response body, but the request failed with status '%s' (%s)",
                    grpc_response.code().name,
                    grpc_response.details(),
                    e=e,
                )
            else:
                logger.info(
                    f"no response body to check due to {grpc_response.code()} response"
                )
            return None

        if not isinstance(result, output_type):
            # Note: This is probably unexpected in some cases
            self._adderr(
                f"response from server ({type(response)}) was not the same type as expected from the registered definition ({output_type})"
            )
            return None

        json_result = json_format.MessageToDict(
            result,
            always_print_fields_with_no_presence=True,
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
