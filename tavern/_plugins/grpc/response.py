import json
import logging

from grpc import StatusCode
from google.protobuf import json_format

from tavern.response.base import BaseResponse
from tavern.util.exceptions import TestFailError

try:
    LoadException = json.decoder.JSONDecodeError
except AttributeError:
    # python 2 raises ValueError on json loads() error instead
    LoadException = ValueError

logger = logging.getLogger(__name__)


class GRPCResponse(BaseResponse):
    def __init__(self, client, name, expected, test_block_config):
        super(GRPCResponse, self).__init__(name, expected, test_block_config)

        self._client = client

        self.received_messages = []

    def __str__(self):
        if self.response:
            return self.response.payload
        else:
            return "<Not run yet>"

    def _validate_block(self, blockname, block):
        """Validate a block of the response

        Args:
            blockname (str): which part of the response is being checked
            block (dict): The actual part being checked
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

        # 'strict' could be a list, in which case we only want to enable strict
        # key checking for that specific bit of the response
        test_strictness = self.test_block_config["strict"]
        if isinstance(test_strictness, list):
            block_strictness = blockname in test_strictness
        else:
            block_strictness = test_strictness

        self.recurse_check_key_match(expected_block, block, blockname, block_strictness)

    def verify(self, response):
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

        if "body" in self.expected:
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
