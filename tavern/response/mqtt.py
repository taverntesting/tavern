import logging

from tavern.schemas.extensions import get_wrapped_response_function
from tavern.util.dict_util import format_keys, recurse_access_key, deep_dict_merge
from tavern.util.exceptions import TestFailError
from .base import BaseResponse, indent_err_text

logger = logging.getLogger(__name__)


class MQTTResponse(BaseResponse):

    def __init__(self, client, name, expected, test_block_config):
        self.name = name

        payload = expected.get("payload")

        if "$ext" in payload:
            self.validate_function = get_wrapped_response_function(payload["$ext"])
        else:
            self.validate_function = None

        self.expected = expected

        super(MQTTResponse, self).__init__()

    def __str__(self):
        if self.response:
            return self.response.payload
        else:
            return "<Not run yet>"

    def verify(self, response):
        """Ensure mqtt message has arrived

        Args:
            response: not used
        """

        self.response = response

        # TODO

        return {}
