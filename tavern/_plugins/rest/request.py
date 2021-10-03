import contextlib
from contextlib import ExitStack
from itertools import filterfalse, tee
import json
import logging
import mimetypes
import os
from urllib.parse import quote_plus
import warnings

from box import Box
import requests
from requests.cookies import cookiejar_from_dict
from requests.utils import dict_from_cookiejar

from tavern._core import exceptions
from tavern._core.dict_util import check_expected_keys, deep_dict_merge, format_keys
from tavern._core.extfunctions import update_from_ext
from tavern._core.report import attach_yaml
from tavern.request import BaseRequest

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

    # pylint: disable=too-many-locals,too-many-statements

    request_args = {}

    # Ones that are required and are enforced to be present by the schema
    required_in_file = ["method", "url"]

    optional_with_default = {"verify": True, "stream": False}

    if "method" not in rspec:
        logger.debug("Using default GET method")
        rspec["method"] = "GET"

    content_keys = ["data", "json", "files", "file_body"]

    in_request = [c for c in content_keys if c in rspec]
    if len(in_request) > 1:
        # Explicitly raise an error here
        # From requests docs:
        # Note, the json parameter is ignored if either data or files is passed.
        # However, we allow the data + files case, as requests handles it correctly
        if set(in_request) != {"data", "files"}:
            raise exceptions.BadSchemaError(
                "Can only specify one type of request data in HTTP request (tried to "
                "send {})".format(" and ".join(in_request))
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

    fspec = format_keys(rspec, test_block_config.variables)

    send_in_body = fspec.get("file_body")
    if send_in_body:
        request_args["file_body"] = send_in_body

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
    add_request_args(RestRequest.optional_in_file, True)

    if "auth" in fspec:
        request_args["auth"] = tuple(fspec["auth"])

    if "cert" in fspec:
        if isinstance(fspec["cert"], list):
            request_args["cert"] = tuple(fspec["cert"])

    if "timeout" in fspec:
        # Needs to be a tuple, it being a list doesn't work
        if isinstance(fspec["timeout"], list):
            request_args["timeout"] = tuple(fspec["timeout"])

    # If there's any nested json in parameters, urlencode it
    # if you pass nested json to 'params' then requests silently fails and just
    # passes the 'top level' key, ignoring all the nested json. I don't think
    # there's a standard way to do this, but urlencoding it seems sensible
    # eg https://openid.net/specs/openid-connect-core-1_0.html#ClaimsParameter
    # > ...represented in an OAuth 2.0 request as UTF-8 encoded JSON (which ends
    # > up being form-urlencoded when passed as an OAuth parameter)
    for key, value in request_args.get("params", {}).items():
        if not isinstance(value, str):
            if key == "$ext":
                logger.debug("Skipping converting of ext function (%s)", value)
                continue

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


def _check_allow_redirects(rspec, test_block_config):
    """
    Check for allow_redirects flag in settings/stage

    Args:
        rspec (dict): request dictionary
        test_block_config (dict): config available for test

    Returns:
        bool: Whether to allow redirects for this stage or not
    """
    # By default, don't follow redirects
    allow_redirects = False

    # Then check to see if we should follow redirects based on settings
    global_follow_redirects = test_block_config.follow_redirects
    if global_follow_redirects is not None:
        allow_redirects = global_follow_redirects

    # ... and test flags
    test_follow_redirects = rspec.pop("follow_redirects", None)
    if test_follow_redirects is not None:
        if global_follow_redirects is not None:
            logger.info(
                "Overriding global follow_redirects setting of %s with test-level specification of %s",
                global_follow_redirects,
                test_follow_redirects,
            )
        allow_redirects = test_follow_redirects

    logger.debug("Allow redirects in stage: %s", allow_redirects)

    return allow_redirects


def _read_expected_cookies(session, rspec, test_block_config):
    """
    Read cookies to inject into request, ignoring others which are present

    Args:
        session (Session): session object
        rspec (dict): test spec
        test_block_config (dict): config available for test

    Returns:
        dict: cookies to use in request, if any
    """
    # Need to do this down here - it is separate from getting request args as
    # it depends on the state of the session
    existing_cookies = session.cookies.get_dict()
    cookies_to_use = format_keys(
        rspec.get("cookies", None), test_block_config.variables
    )

    if cookies_to_use is None:
        logger.debug("No cookies specified in request, sending all")
        return None
    elif cookies_to_use in ([], {}):
        logger.debug("Not sending any cookies with request")
        return {}

    def partition(pred, iterable):
        """From itertools documentation"""
        t1, t2 = tee(iterable)
        return list(filterfalse(pred, t1)), list(filter(pred, t2))

    # Cookies are either a single list item, specitying which cookie to send, or
    # a mapping, specifying cookies to override
    expected, extra = partition(lambda x: isinstance(x, dict), cookies_to_use)

    missing = set(expected) - set(existing_cookies.keys())

    if missing:
        logger.error("Missing cookies")
        raise exceptions.MissingCookieError(
            "Tried to use cookies '{}' in request but only had '{}' available".format(
                expected, existing_cookies
            )
        )

    # 'extra' should be a list of dictionaries - merge them into one here
    from_extra = {k: v for mapping in extra for (k, v) in mapping.items()}

    if len(extra) != len(from_extra):
        logger.error("Duplicate cookie override values specified")
        raise exceptions.DuplicateCookieError(
            "Tried to override the value of a cookie multiple times in one request"
        )

    overwritten = [i for i in expected if i in from_extra]

    if overwritten:
        logger.error("Duplicate cookies found in request")
        raise exceptions.DuplicateCookieError(
            "Asked to use cookie {} from previous request but also redefined it as {}".format(
                overwritten, from_extra
            )
        )

    from_cookiejar = {c: existing_cookies.get(c) for c in expected}

    return deep_dict_merge(from_cookiejar, from_extra)


def _read_filespec(filespec):
    """
    Get configuration for uploading file

    Can either be just a path to a file or a 'long' format including content type/encoding

    Args:
        filespec: Either a string with the path to a file or a dictionary with file_path and possible content_type and/or content_encoding

    Returns:
        tuple: (file path, content type, content encoding)
    """
    if isinstance(filespec, str):
        return filespec, None, None
    elif isinstance(filespec, dict):
        return (
            filespec.get("file_path"),
            filespec.get("content_type"),
            filespec.get("content_encoding"),
        )
    else:
        # Could remove, also done in schema check
        raise exceptions.BadSchemaError(
            "File specification must be a path or a dictionary"
        )


def _get_file_arguments(request_args, stack, test_block_config):
    """Get corect arguments for anything that should be passed as a file to
    requests

    Args:
        test_block_config (dict): config for test
        stack (ExitStack): context stack to add file objects to so they're
            closed correctly after use

    Returns:
        dict: mapping of {"files": ...} to pass directly to requests
    """

    files_to_send = {}

    for key, filespec in request_args.get("files", {}).items():
        if not mimetypes.inited:
            mimetypes.init()

        filepath, content_type, encoding = _read_filespec(filespec)
        filepath = format_keys(filepath, test_block_config.variables)

        filename = os.path.basename(filepath)

        # a 2-tuple ('filename', fileobj)
        file_spec = [filename, stack.enter_context(open(filepath, "rb"))]

        # Try to guess as well, but don't override what the user specified
        guessed_content_type, guessed_encoding = mimetypes.guess_type(filepath)
        content_type = content_type or guessed_content_type
        encoding = encoding or guessed_encoding

        # If it doesn't have a mimetype, or can't guess it, don't
        # send the content type for the file
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


class RestRequest(BaseRequest):
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

        if rspec.pop("clear_session_cookies", False):
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
            "file_body",
            "stream",
            "timeout",
            "cookies",
            "cert",
            # "hooks",
            "follow_redirects",
        }

        check_expected_keys(expected, rspec)

        request_args = get_request_args(rspec, test_block_config)
        update_from_ext(
            request_args,
            RestRequest.optional_in_file,
        )

        # Used further down, but pop it asap to avoid unwanted side effects
        file_body = request_args.pop("file_body", None)

        # If there was a 'cookies' key, set it in the request
        expected_cookies = _read_expected_cookies(session, rspec, test_block_config)
        if expected_cookies is not None:
            logger.debug("Sending cookies %s in request", expected_cookies.keys())
            request_args.update(cookies=expected_cookies)

        # Check for redirects
        request_args.update(
            allow_redirects=_check_allow_redirects(rspec, test_block_config)
        )

        logger.debug("Request args: %s", request_args)

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

                # These are mutually exclusive
                if file_body:
                    file = stack.enter_context(open(file_body, "rb"))
                    request_args.update(data=file)
                else:
                    self._request_args.update(
                        _get_file_arguments(request_args, stack, test_block_config)
                    )

                return session.request(**self._request_args)

        self._prepared = prepared_request

    def run(self):
        """Runs the prepared request and times it

        Todo:
            time it

        Returns:
            requests.Response: response object
        """

        attach_yaml(
            self._request_args,
            name="rest_request",
        )

        try:
            return self._prepared()
        except requests.exceptions.RequestException as e:
            logger.exception("Error running prepared request")
            raise exceptions.RestRequestException from e

    @property
    def request_vars(self):
        return Box(self._request_args)
