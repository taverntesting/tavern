import json
import importlib
import logging
import re
import jwt
from box import Box

from tavern.schemas.files import wrapfile, verify_generic


logger = logging.getLogger(__name__)


def check_exception_raised(response, exception_location):
    """ Make sure the result from the server is the same as the exception we
    expect to raise

    Args:
        response (requests.Response): response object
        exception_location (str): entry point style location of exception
    """

    dumped = json.loads(response.content.decode("utf8"))

    module_name, exception_name = exception_location.split(":")
    module = importlib.import_module(module_name)
    exception = getattr(module, exception_name)

    if "title" in dumped:
        assert dumped["title"] == exception.error_title
    elif "error" in dumped:
        assert dumped["error"] == exception.error_title

    actual_description = dumped.get("description", dumped.get("error_description"))
    expected_description = getattr(exception, "error_description", getattr(exception, "description"))

    try:
        assert actual_description == expected_description
    except AssertionError:
        # If it has a format, ignore this error. Would be annoying to say how to
        # format things in the validator, especially if it's a set/dict which is
        # unordered
        if not any(i in expected_description for i in "{}"):
            raise

    assert response.status_code == int(exception.status.split()[0])


def validate_jwt(response, jwt_key, **kwargs):
    """Make sure a jwt is valid

    This uses the pyjwt library to decode the jwt, so any keyword args needed
    should be passed as per that library. You will probably want to use
    verify_signature=False unless using a HMAC key because it can be a bit
    verbose to pass in a public key.

    This also returns the jwt so it can be used both to verify and save jwts -
    it wraps this in a Box so it can also be used for future formatting

    Args:
        response (Response): requests.Response object
        jwt_key (str): key of jwt in body of request
        **kwargs: Any extra arguments to pass to jwt.decode

    Returns:
        dict: dictionary of jwt: boxed jwt claims
    """
    token = response.json()[jwt_key]
    decoded = jwt.decode(token, **kwargs)

    logger.debug("Decoded jwt to %s", decoded)

    return {"jwt": Box(decoded)}


def validate_pykwalify(response, schema):
    """Make sure the response matches a given schema

    Args:
        response (Response): reqeusts.Response object
        schema (dict): Schema for response
    """
    with wrapfile(response.json()) as rdump, wrapfile(schema) as sdump:
        verify_generic(rdump, sdump)


def validate_regex(response, expression):
    """Make sure the response body matches a regex expression

    Args:
        response (Response): reqeusts.Response object
        expression (str): Regex expression to use
    Returns:
        dict: dictionary of regex: boxed name capture groups
    """
    match = re.search(expression, response.text)

    assert match

    return {
        "regex": Box(match.groupdict())
    }
