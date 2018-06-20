import logging

import requests
from future.utils import raise_from

from tavern.util.dict_util import format_keys
from tavern.plugins import PluginHelperBase
from tavern.util import exceptions

from .request import RestRequest
from .response import RestResponse


logger = logging.getLogger(__name__)


class TavernRestPlugin(PluginHelperBase):
    session_type = requests.Session

    request_type = RestRequest
    request_block_name = "request"

    @staticmethod
    def get_expected_from_request(stage, test_block_config, session):
        # pylint: disable=unused-argument
        try:
            r_expected = stage["response"]
        except KeyError as e:
            logger.error("Need a 'response' block if a 'request' is being sent")
            raise_from(exceptions.MissingSettingsError, e)

        f_expected = format_keys(r_expected, test_block_config["variables"])
        return f_expected

    verifier_type = RestResponse
    response_block_name = "response"
