import json
import importlib
import logging
import re
import jwt
import jmespath

from future.utils import raise_from
from box import Box

from tavern.util import exceptions
from tavern.testutils.jmesutils import validate_comparision, actual_validation
from tavern.schemas.files import wrapfile, verify_generic
from tavern.util.dict_util import check_keys_match_recursive

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


def validate_regex(response, expression, header=None):
    """Make sure the response matches a regex expression

    Args:
        response (Response): requests.Response object
        expression (str): Regex expression to use
        header (str): Match against a particular header instead of the body
    Returns:
        dict: dictionary of regex: boxed name capture groups
    """
    if header:
        content = response.headers[header]
    else:
        content = response.text

    match = re.search(expression, content)
    assert match

    return {
        "regex": Box(match.groupdict())
    }


def validate_content(response, comparisions):
    """Asserts expected value with actual value using JMES path expression

    Args:
        response (Response): reqeusts.Response object.
        comparisions(list):
            A list of dict containing the following keys:
                1. jmespath : JMES path expression to extract data from.
                2. operator : Operator to use to compare data.
                3. expected : The expected value to match for
    """
    for each_comparision in comparisions:
        path, _operator, expected = validate_comparision(each_comparision)
        logger.debug("Searching for '%s' in '%s'", path, response.json())
        actual = jmespath.search(path, response.json())

        if actual is None:
            raise exceptions.JMESError("JMES path '{}' not found in response".format(path))

        expession = " ".join([str(path), str(_operator), str(expected)])
        parsed_expession = " ".join([str(actual), str(_operator), str(expected)])

        if _operator == "eq" and 0:
            check_keys_match_recursive(expected, actual, [])
        else:
            try:
                actual_validation(_operator, actual, expected, parsed_expession, expession)
            except AssertionError as e:
                raise_from(exceptions.JMESError("Error validating JMES"), e)
