import contextlib
import json
import logging
import mimetypes
import os
import warnings

try:
    from urllib.parse import quote_plus
except ImportError:
    from urllib import quote_plus  # type: ignore

from contextlib2 import ExitStack
from future.utils import raise_from
import requests
from requests.cookies import cookiejar_from_dict
from requests.utils import dict_from_cookiejar
from box import Box

from tavern.util import exceptions
from tavern.util.dict_util import format_keys, check_expected_keys
from tavern.schemas.extensions import get_wrapped_create_function

from tavern.request.base import BaseRequest

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

    # pylint: disable=too-many-locals

    request_args = {}

    # Ones that are required and are enforced to be present by the schema
    required_in_file = ["method", "url"]

    optional_in_file = [
        "json",
        "data",
        "params",
        "headers",
        "files",
        "timeout",
        "cert",
        # Ideally this would just be passed through but requests seems to error
        # if we pass a list instead of a tuple, so we have to manually convert
        # it further down
        # "auth"
    ]

    optional_with_default = {"verify": True, "stream": False}

    if "method" not in rspec:
        logger.debug("Using default GET method")
        rspec["method"] = "GET"

    content_keys = ["data", "json", "files"]

    in_request = [c for c in content_keys if c in rspec]
    if len(in_request) > 1:
        # Explicitly raise an error here
        # From requests docs:
        # Note, the json parameter is ignored if either data or files is passed.
        raise exceptions.BadSchemaError(
            "Can only specify one type of request data in HTTP request (tried to send {})".format(
                " and ".join(in_request)
            )
        )

    headers = rspec.get("headers", {})
    has_content_header = "content-type" in [h.lower() for h in headers.keys()]

    if "files" in rspec:
        if has_content_header:
            logger.warning(
                "Tried to specify a content-type header while sending a file - this will be ignored"
            )
            rspec["headers"] = {
                i: j for i, j in headers.items() if i.lower() != "content-type"
            }

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

    if "auth" in fspec:
        request_args["auth"] = tuple(fspec["auth"])

    if "cert" in fspec:
        if isinstance(fspec["cert"], list):
            request_args["cert"] = tuple(fspec["cert"])

    if "timeout" in fspec:
        # Needs to be a tuple, it being a list doesn't work
        if isinstance(fspec["timeout"], list):
            request_args["timeout"] = tuple(fspec["timeout"])

    for key in optional_in_file:
        try:
            func = get_wrapped_create_function(request_args[key].pop("$ext"))
        except (KeyError, TypeError, AttributeError):
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
    # "cookies",

    # These verbs _can_ send a body but the body _should_ be ignored according
    # to the specs - some info here:
    # https://developer.mozilla.org/en-US/docs/Web/HTTP/Methods
    if request_args["method"] in ["GET", "HEAD", "OPTIONS"]:
        if any(i in request_args for i in ["json", "data"]):
            warnings.warn(
                "You are trying to send a body with a HTTP verb that has no semantic use for it",
                RuntimeWarning,
            )

    return request_args


@contextlib.contextmanager
def _set_cookies_for_request(session, request_args):
    """
    Possibly reset session cookies for a single request then set them back.
    If no cookies were present in the request arguments, do nothing.

    This does not use try/finally because if it fails then we don't care about
    the cookies anyway

    Args:
        session (requests.Session): Current session
        request_args (dict): current request arguments
    """
    if "cookies" in request_args:
        old_cookies = dict_from_cookiejar(session.cookies)
        session.cookies = cookiejar_from_dict({})
        yield
        session.cookies = cookiejar_from_dict(old_cookies)
    else:
        yield


class RestRequest(BaseRequest):
    def __init__(self, session, rspec, test_block_config):
        """Prepare request

        Args:
            session (requests.Session): existing session
            rspec (dict): test spec
            test_block_config (dict): Any configuration for this the block of
                tests

        Raises:
            UnexpectedKeysError: If some unexpected keys were used in the test
                spec. Only valid keyword args to requests can be passed
        """

        if "meta" in rspec:
            meta = rspec.pop("meta")
            if meta and "clear_session_cookies" in meta:
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
            "files",
            "stream",
            "timeout",
            "cookies",
            "cert",
            # "hooks",
        }

        check_expected_keys(expected, rspec)

        request_args = get_request_args(rspec, test_block_config)

        # Need to do this down here - it is separate from getting request args as
        # it depends on the state of the session
        if "cookies" in rspec:
            existing_cookies = session.cookies.get_dict()
            missing = set(rspec["cookies"]) - set(existing_cookies.keys())
            if missing:
                logger.error("Missing cookies")
                raise exceptions.MissingCookieError(
                    "Tried to use cookies '{}' in request but only had '{}' available".format(
                        rspec["cookies"], existing_cookies
                    )
                )
            request_args["cookies"] = {
                c: existing_cookies.get(c) for c in rspec["cookies"]
            }

        logger.debug("Request args: %s", request_args)

        request_args.update(allow_redirects=False)

        self._request_args = request_args

        # There is no way using requests to make a prepared request that will
        # not follow redirects, so instead we have to do this. This also means
        # that we can't have the 'pre-request' hook any more because we don't
        # create a prepared request.

        def prepared_request():
            # If there are open files, create a context manager around each so
            # they will be closed at the end of the request.
            with ExitStack() as stack:
                stack.enter_context(_set_cookies_for_request(session, request_args))
                self._request_args.update(self._get_file_arguments(stack))
                return session.request(**self._request_args)

        self._prepared = prepared_request

    def _get_file_arguments(self, stack):
        """Get corect arguments for anything that should be passed as a file to
        requests

        Args:
            stack (ExitStack): context stack to add file objects to so they're
                closed correctly after use

        Returns:
            dict: mapping of {"files": ...} to pass directly to requests
        """

        files_to_send = {}

        for key, filepath in self._request_args.get("files", {}).items():
            if not mimetypes.inited:
                mimetypes.init()

            filename = os.path.basename(filepath)

            # a 2-tuple ('filename', fileobj)
            file_spec = [filename, stack.enter_context(open(filepath, "rb"))]

            # If it doesn't have a mimetype, or can't guess it, don't
            # send the content type for the file
            content_type, encoding = mimetypes.guess_type((filepath))
            if content_type:
                # a 3-tuple ('filename', fileobj, 'content_type')
                logger.debug("content_type for '%s' = '%s'", filename, content_type)
                file_spec.append(content_type)
                if encoding:
                    # or a 4-tuple ('filename', fileobj, 'content_type', custom_headers)
                    logger.debug("encoding for '%s' = '%s'", filename, encoding)
                    # encoding is None for no encoding or the name of the
                    # program used to encode (e.g. compress or gzip). The
                    # encoding is suitable for use as a Content-Encoding header.
                    file_spec.append({"Content-Encoding": encoding})

            files_to_send[key] = tuple(file_spec)

        if files_to_send:
            return {"files": files_to_send}
        else:
            return {}

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
