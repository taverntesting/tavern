import logging

import requests

from tavern._core import exceptions
from tavern._core.dict_util import format_keys
from tavern._core.plugins import PluginHelperBase

from .request import RestRequest
from .response import RestResponse

logger = logging.getLogger(__name__)


class TavernRestPlugin(PluginHelperBase):
    session_type = requests.Session

    request_type = RestRequest
    request_block_name = "request"

    @staticmethod
    def get_expected_from_request(
        response_block, test_block_config, session
    ):  # pylint: disable=unused-argument
        if response_block is None:
            raise exceptions.MissingSettingsError(
                "no response block specified for HTTP test stage"
            )

        f_expected = format_keys(response_block, test_block_config.variables)
        return f_expected

    verifier_type = RestResponse
    response_block_name = "response"
