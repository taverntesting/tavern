import functools
import logging

import requests

from .util import exceptions
from .util.dict_util import format_keys
from .schemas.extensions import get_wrapped_create_function

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

    try:
        fspec = format_keys(rspec, test_block_config["variables"])
    except exceptions.MissingFormatError as e:
        logger.error("Key(s) not found in format: %s", e.args)
        raise

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
        except KeyError:
            pass
        else:
            request_args[key] = func()

    for key, val in optional_with_default.items():
        request_args[key] = fspec.get(key, val)

    # TODO
    # requests takes all of these - we need to parse the input to get them
    # "files",
    # "auth",
    # "cookies",

    if request_args["method"] == "GET":
        if any(i in request_args for i in ["json", "data"]):
            raise exceptions.BadSchemaError("Can't add json or urlencoded data to a GET request - use query parameters instead?")

    return request_args


class TRequest(object):

    def __init__(self, rspec, test_block_config):
        """Prepare request

        Args:
            rspec (dict): test spec
            test_block_config (dict): Any configuration for this the block of
                tests

        Raises:
            UnexpectedKeysError: If some unexpected keys were used in the test
                spec. Only valid keyword args to requests can be passed
        """

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

        keyset = set(rspec)

        if not keyset <= expected:
            unexpected = keyset - expected

            msg = "Unexpected keys {}".format(unexpected)
            logger.error(msg)
            raise exceptions.UnexpectedKeysError(msg)

        request_args = get_request_args(rspec, test_block_config)

        logger.debug("Request args: %s", request_args)

        request_args.update(allow_redirects=False)

        # There is no way using requests to make a prepared request that will
        # not follow redicrects, so instead we have to do this. This also means
        # that we can't have the 'pre-request' hook any more because we don't
        # create a prepared request.
        self._session = requests.Session()
        self._prepared = functools.partial(self._session.request, **request_args)

    def run(self):
        """ Runs the prepared request and times it

        Todo:
            time it

        Returns:
            requests.Response: response object
        """

        return self._prepared()
