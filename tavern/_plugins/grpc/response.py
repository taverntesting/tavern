import logging
from typing import Mapping, Union

import grpc
from google.protobuf import json_format
from grpc import StatusCode

from tavern._core.exceptions import TestFailError
from tavern._core.pytest.config import TestConfig
from tavern.response import BaseResponse

logger = logging.getLogger(__name__)


class GRPCResponse(BaseResponse):
    def __init__(
        self, client, name: str, expected: Mapping, test_block_config: TestConfig
    ):
        super(GRPCResponse, self).__init__(name, expected, test_block_config)

        self._client = client

    def __str__(self):
        if self.response:
            return self.response.payload
        else:
            return "<Not run yet>"

    def _validate_block(self, blockname: str, block: Mapping):
        """Validate a block of the response

        Args:
            blockname: which part of the response is being checked
            block: The actual part being checked
        """
        try:
            expected_block = self.expected[blockname] or {}
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

    def verify(self, response: Union[grpc.Call, grpc.Future]) -> Mapping:
        logger.debug(f"grpc status code: {response.code()}")
        logger.debug(f"grpc details: {response.details()}")

        # Get any keys to save
        saved = {}
        verify_status = [StatusCode.OK.name]
        if "status" in self.expected:
            status = self.expected["status"]
            if isinstance(status, list):
                verify_status = [name.upper() for name in status]
            else:
                verify_status = [status.upper()]

        if response.code().name not in verify_status:
            self._adderr(
                "expected status %s, but the actual response '%s'",
                verify_status,
                response.code().name,
            )

        if "details" in self.expected:
            verify_details = self.expected["details"]
            if verify_details != response.details():
                self._adderr(
                    "expected details '%s', but the actual response '%s'",
                    verify_details,
                    response.details(),
                )

        if "proto_body" in self.expected:
            result = response.result()

            json_result = json_format.MessageToDict(
                result,
                including_default_value_fields=True,
                preserving_proto_field_name=True,
            )

            self._validate_block("body", json_result)
            self._maybe_run_validate_functions(json_result)

            saved.update(
                self.maybe_get_save_values_from_save_block("body", json_result)
            )
            saved.update(
                self.maybe_get_save_values_from_ext(json_result, self.expected)
            )

        if self.errors:
            raise TestFailError(
                "Test '{:s}' failed:\n{:s}".format(self.name, self._str_errors()),
                failures=self.errors,
            )

        return saved
