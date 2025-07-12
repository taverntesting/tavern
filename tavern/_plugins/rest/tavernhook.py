"""
Tavern REST TavernHook Plugin

This module provides the tavernhook functionality for REST requests in the Tavern testing framework.
It handles the integration between Tavern and the REST request system.

The module contains the tavernhook classes and functions that enable Tavern to
properly handle REST request execution and response processing.
"""

import logging

import requests

from tavern._core import exceptions
from tavern._core.dict_util import format_keys
from tavern._core.plugins import PluginHelperBase
from tavern._core.pytest.config import TestConfig

from .request import RestRequest
from .response import RestResponse

logger: logging.Logger = logging.getLogger(__name__)


class TavernRestPlugin(PluginHelperBase):
    """REST tavernhook plugin for Tavern.

    This class provides the tavernhook functionality for REST requests,
    handling the integration between Tavern and the REST request system.
    """
    session_type = requests.Session

    request_type = RestRequest
    request_block_name = "request"

    @staticmethod
    def get_expected_from_request(
        response_block: dict, test_block_config: TestConfig, _session
    ):
        """Get expected response from request configuration.

        Args:
            response_block: Response block configuration
            test_block_config: Test configuration
            session: Session object

        Returns:
            Formatted expected response configuration

        Raises:
            MissingSettingsError: If no response block is specified
        """
        if response_block is None:
            raise exceptions.MissingSettingsError(
                "no response block specified for HTTP test stage"
            )

        f_expected = format_keys(response_block, test_block_config.variables)
        return f_expected

    verifier_type = RestResponse
    response_block_name = "response"
