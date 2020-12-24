import logging

from google.protobuf import json_format
from grpc import StatusCode

from tavern.response.base import BaseResponse
from tavern.util.exceptions import TestFailError

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
