import importlib
import json
import logging
import re

from box import Box
import jmespath
import jwt

from tavern._core import exceptions
from tavern._core.dict_util import check_keys_match_recursive, recurse_access_key
from tavern._core.jmesutils import actual_validation, validate_comparison
from tavern._core.schema.files import verify_pykwalify

logger = logging.getLogger(__name__)


def check_exception_raised(response, exception_location):
    """Make sure the result from the server is the same as the exception we
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
    expected_description = getattr(
        exception, "error_description", getattr(exception, "description")
    )

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
    try:
        to_verify = response.json()
    except TypeError as e:
        raise exceptions.BadSchemaError(
            "Tried to match a pykwalify schema against a non-json response"
        ) from e

    else:
        verify_pykwalify(to_verify, schema)


def validate_regex(response, expression, *, header=None, in_jmespath=None):
    """Make sure the response matches a regex expression

    Args:
        response (requests.Response): requests.Response object
        expression (str): Regex expression to use
        header (str): Match against a particular header instead of the body
        in_jmespath (str): if present, jmespath to access before trying to match

    Returns:
        dict: dictionary of regex: boxed name capture groups
    """

    if header and in_jmespath:
        raise exceptions.BadSchemaError("Can only specify one of header or jmespath")

    if header:
        content = response.headers[header]
    else:
        content = response.text

    if in_jmespath:
        if not response.headers.get("content-type", "").startswith("application/json"):
            logger.warning(
                "Trying to use jmespath match but content type is not application/json"
            )

        try:
            decoded = json.loads(content)
        except json.JSONDecodeError as e:
            raise exceptions.RegexAccessError(
                "unable to decode json for regex match"
            ) from e

        content = recurse_access_key(decoded, in_jmespath)
        if not isinstance(content, str):
            raise exceptions.RegexAccessError(
                "Successfully accessed {} from response, but it was a {} and not a string".format(
                    in_jmespath, type(content)
                )
            )

    logger.debug("Matching %s with %s", content, expression)

    match = re.search(expression, content)
    if match is None:
        raise exceptions.RegexAccessError("No match for regex")

    return {"regex": Box(match.groupdict())}


def validate_content(response, comparisons):
    """Asserts expected value with actual value using JMES path expression

    Args:
        response (Response): reqeusts.Response object.
        comparisons(list):
            A list of dict containing the following keys:
                1. jmespath : JMES path expression to extract data from.
                2. operator : Operator to use to compare data.
                3. expected : The expected value to match for
    """
    for each_comparison in comparisons:
        path, _operator, expected = validate_comparison(each_comparison)
        logger.debug("Searching for '%s' in '%s'", path, response.json())

        actual = jmespath.search(path, response.json())

        expession = " ".join([str(path), str(_operator), str(expected)])
        parsed_expession = " ".join([str(actual), str(_operator), str(expected)])

        if _operator == "eq" and 0:
            check_keys_match_recursive(expected, actual, [])
        else:
            try:
                actual_validation(
                    _operator, actual, expected, parsed_expession, expession
                )
            except AssertionError as e:
                raise exceptions.JMESError("Error validating JMES") from e


def check_jmespath_match(parsed_response, query, expected=None):
    """
    Check that the JMES path given in 'query' is present in the given response

    Args:
        parsed_response (dict, list): Response list or dict
        query (str): JMES query
        expected (str, optional): Possible value to match against. If None,
            'query' will just check that _something_ is present
    """
    actual = jmespath.search(query, parsed_response)

    msg = "JMES path '{}' not found in response".format(query)

    if actual is None:
        raise exceptions.JMESError(msg)

    if expected is not None:
        # Reuse dict util helper as it should behave the same
        check_keys_match_recursive(expected, actual, [], True)
    elif not actual and not (actual == expected):  # pylint: disable=superfluous-parens
        # This can return an empty list, but it might be what we expect. if not,
        # raise an exception
        raise exceptions.JMESError(msg)

    return actual
