import functools
import logging

from future.utils import raise_from
import requests
from box import Box

from tavern.util import exceptions
from tavern.util.dict_util import check_expected_keys
from tavern._plugins.rest.request import get_request_args

from tavern.request.base import BaseRequest

logger = logging.getLogger(__name__)


class FlaskRequest(BaseRequest):

    def __init__(self, session, rspec, test_block_config):
        """Prepare request

        Args:
            rspec (dict): test spec
            test_block_config (dict): Any configuration for this the block of
                tests

        Raises:
            UnexpectedKeysError: If some unexpected keys were used in the test
                spec. Only valid keyword args to requests can be passed
        """

        if 'meta' in rspec:
            meta = rspec.pop('meta')
            if meta and 'clear_session_cookies' in meta:
                session.cookies.clear_session_cookies()

        expected = {
            "method",
            "url",
            "headers",
            "data",
            "params",
            "auth",
            "json",
            "verify",
            # "files",
            # "cookies",
            # "hooks",
        }

        check_expected_keys(expected, rspec)

        request_args = get_request_args(rspec, test_block_config)

        logger.debug("Request args: %s", request_args)

        request_args.update(allow_redirects=False)

        self._request_args = request_args

        # There is no way using requests to make a prepared request that will
        # not follow redicrects, so instead we have to do this. This also means
        # that we can't have the 'pre-request' hook any more because we don't
        # create a prepared request.
        self._prepared = functools.partial(session.request, **request_args)

    def run(self):
        """ Runs the prepared request and times it

        Todo:
            time it

        Returns:
            requests.Response: response object
        """

        try:
            return self._prepared()
        except requests.exceptions.RequestException as e:
            logger.exception("Error running prepared request")
            raise_from(exceptions.RestRequestException, e)

    @property
    def request_vars(self):
        return Box(self._request_args)
