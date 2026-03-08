import logging
from os.path import abspath, dirname, join

import requests
import yaml

from tavern._core import exceptions
from tavern._core.dict_util import format_keys
from tavern._core.plugins import PluginHelperBase
from tavern._core.pytest.config import TestConfig

from .request import RestRequest
from .response import RestResponse

logger: logging.Logger = logging.getLogger(__name__)


class TavernRestPlugin(PluginHelperBase):
    session_type = requests.Session

    request_type = RestRequest
    request_block_name = "request"

    schema: dict
    has_multiple_responses = False

    @staticmethod
    def get_expected_from_request(
        response_block: dict, test_block_config: TestConfig, session
    ):
        if response_block is None:
            raise exceptions.MissingSettingsError(
                "no response block specified for HTTP test stage"
            )

        f_expected = format_keys(response_block, test_block_config.variables)
        return f_expected

    verifier_type = RestResponse
    response_block_name = "response"


schema_path: str = join(abspath(dirname(__file__)), "jsonschema.yaml")
with open(schema_path, encoding="utf-8") as schema_file:
    schema = yaml.load(schema_file, Loader=yaml.SafeLoader)

TavernRestPlugin.schema = schema
