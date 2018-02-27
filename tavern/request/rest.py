import functools
import json
import logging
import warnings

try:
    from urllib.parse import quote_plus
except ImportError:
    from urllib import quote_plus

from future.utils import raise_from
import requests
from box import Box

from tavern.util import exceptions
from tavern.util.dict_util import format_keys, check_expected_keys
from tavern.schemas.extensions import get_wrapped_create_function

from .base import BaseRequest

logger = logging.getLogger(__name__)


def get_request_args(rspec, test_block_config):
    """Format the test spec given values inthe global config

    Todo:
        Add similar functionality to validate/save $ext functions so input
        can be generated from a function

    Args:
        rspec (dict): Test spec
        test_block_config (dict): Test block config

    Returns:
        dict: Formatted test spec

    Raises:
        BadSchemaError: Tried to pass a body in a GET request
    """

    request_args = {}

    # Ones that are required and are enforced to be present by the schema
    required_in_file = [
        "method",
        "url",
    ]

    optional_in_file = [
        "json",
        "data",
        "params",
        "headers",
    ]

    optional_with_default = {
        "verify": True,
    }

    if "method" not in rspec:
        logger.debug("Using default GET method")
        rspec["method"] = "GET"

    headers = rspec.get("headers")
    if headers:
        if "content-type" not in [h.lower() for h in headers.keys()]:
            rspec["headers"]["content-type"] = "application/json"

    fspec = format_keys(rspec, test_block_config["variables"])

    def add_request_args(keys, optional):
        for key in keys:
            try:
                request_args[key] = fspec[key]
            except KeyError:
                if optional or (key in request_args):
                    continue

                # This should never happen
                raise

    add_request_args(required_in_file, False)
    add_request_args(optional_in_file, True)

    for key in optional_in_file:
        try:
            func = get_wrapped_create_function(request_args[key].pop("$ext"))
        except (KeyError, TypeError):
            pass
        else:
            request_args[key] = func()

    # If there's any nested json in parameters, urlencode it
    # if you pass nested json to 'params' then requests silently fails and just
    # passes the 'top level' key, ignoring all the nested json. I don't think
    # there's a standard way to do this, but urlencoding it seems sensible
    # eg https://openid.net/specs/openid-connect-core-1_0.html#ClaimsParameter
    # > ...represented in an OAuth 2.0 request as UTF-8 encoded JSON (which ends
    # > up being form-urlencoded when passed as an OAuth parameter)
    for key, value in request_args.get("params", {}).items():
        if isinstance(value, dict):
            request_args["params"][key] = quote_plus(json.dumps(value))

    for key, val in optional_with_default.items():
        request_args[key] = fspec.get(key, val)

    # TODO
    # requests takes all of these - we need to parse the input to get them
    # "files",
    # "cookies",

    # These verbs _can_ send a body but the body _should_ be ignored according
    # to the specs - some info here:
    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods
    if request_args["method"] in ["GET", "HEAD", "OPTIONS"]:
        if any(i in request_args for i in ["json", "data"]):
            warnings.warn("You are trying to send a body with a HTTP verb that has no semantic use for it", RuntimeWarning)

    return request_args


class RestRequest(BaseRequest):

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
