import logging
import re
import functools
import importlib

from future.utils import raise_from

from tavern.util.exceptions import BadSchemaError
from tavern.util import exceptions
from tavern.util.loader import ApproxScalar


logger = logging.getLogger(__name__)


def import_ext_function(entrypoint):
    """Given a function name in the form of a setuptools entry point, try to
    dynamically load and return it

    Args:
        entrypoint (str): setuptools-style entrypoint in the form
            module.submodule:function

    Returns:
        function: function loaded from entrypoint

    Raises:
        InvalidExtFunctionError: If the module or function did not exist
    """
    try:
        module, funcname = entrypoint.split(":")
    except ValueError as e:
        msg = "Expected entrypoint in the form module.submodule:function"
        logger.exception(msg)
        raise_from(exceptions.InvalidExtFunctionError(msg), e)

    try:
        module = importlib.import_module(module)
    except ImportError as e:
        msg = "Error importing module {}".format(module)
        logger.exception(msg)
        raise_from(exceptions.InvalidExtFunctionError(msg), e)

    try:
        function = getattr(module, funcname)
    except AttributeError as e:
        msg = "No function named {} in {}".format(funcname, module)
        logger.exception(msg)
        raise_from(exceptions.InvalidExtFunctionError(msg), e)

    return function


def get_wrapped_response_function(ext):
    """Wraps a ext function with arguments given in the test file

    This is similar to functools.wrap, but this makes sure that 'response' is
    always the first argument passed to the function

    Args:
        ext (dict): $ext function dict with function, extra_args, and
            extra_kwargs to pass

    Returns:
        function: Wrapped function
    """
    args = ext.get("extra_args") or ()
    kwargs = ext.get("extra_kwargs") or {}
    func = import_ext_function(ext["function"])

    @functools.wraps(func)
    def inner(response):
        return func(response, *args, **kwargs)

    inner.func = func

    return inner


def get_wrapped_create_function(ext):
    """Same as above, but don't require a response
    """
    args = ext.get("extra_args") or ()
    kwargs = ext.get("extra_kwargs") or {}
    func = import_ext_function(ext["function"])

    @functools.wraps(func)
    def inner():
        return func(*args, **kwargs)

    inner.func = func

    return inner


def validate_extensions(value, rule_obj, path):
    """Given a specification for calling a validation function, make sure that
    the arguments are valid (ie, function is valid, arguments are of the
    correct type...)

    Arguments/return values are sort of pykwalify internals (this function is
    only called from pykwalify) so not listed

    Todo:
        Because this is loaded by pykwalify as a file, we need some kind of
        entry point to set up logging. Or just fork pykwalify and fix the
        various issues in it.

        We should also check the function signature using the `inspect` module

    Raises:
        BadSchemaError: Something in the validation function spec was wrong
    """
    # pylint: disable=unused-argument

    try:
        iter(value)
    except TypeError as e:
        raise_from(BadSchemaError("Invalid value for key - things like body/params/headers/data have to be iterable (list, dictionary, string), not a single value"), e)

    if isinstance(value, dict) and "$ext" in value:
        expected_keys = {
            "function",
            "extra_args",
            "extra_kwargs",
        }

        validate_keys = value["$ext"]

        extra = set(validate_keys) - expected_keys
        if extra:
            raise BadSchemaError("Unexpected keys passed to $ext: {}".format(extra))

        if "function" not in validate_keys:
            raise BadSchemaError("No function specified for validation")

        try:
            import_ext_function(validate_keys["function"])
        except Exception as e: # pylint: disable=broad-except
            raise_from(BadSchemaError("Couldn't load {}".format(validate_keys["function"])), e)

        extra_args = validate_keys.get("extra_args")
        extra_kwargs = validate_keys.get("extra_kwargs")

        if extra_args and not isinstance(extra_args, list):
            raise BadSchemaError("Expected a list of extra_args, got {}".format(type(extra_args)))

        if extra_kwargs and not isinstance(extra_kwargs, dict):
            raise BadSchemaError("Expected a dict of extra_kwargs, got {}".format(type(extra_args)))

    return True


def validate_status_code_is_int_or_list_of_ints(value, rule_obj, path):
    # pylint: disable=unused-argument
    err_msg = "status_code has to be an integer or a list of integers (got {})".format(value)

    if not isinstance(value, (int, list)):
        raise BadSchemaError(err_msg)

    if isinstance(value, list):
        if not all(isinstance(i, int) for i in value):
            raise BadSchemaError(err_msg)

    return True


def check_usefixtures(value, rule_obj, path):
    # pylint: disable=unused-argument
    err_msg = "'usefixtures' has to be a list with at least one item"

    if not isinstance(value, (list, tuple)):
        raise BadSchemaError(err_msg)

    if not value:
        raise BadSchemaError(err_msg)

    return True


def validate_data_key_with_ext_function(value, rule_obj, path):
    """Validate the 'data' key in a http request

    From requests docs:

    > data - (optional) Dictionary or list of tuples [(key, value)] (will be
    > form-encoded), bytes, or file-like object to send in the body of the
    > Request.

    We could handle lists of tuples, but it seems entirely pointless to maintain
    compatibility for something which is more verbose and does the same thing
    """
    validate_extensions(value, rule_obj, path)

    if isinstance(value, dict):
        # Fine
        pass
    elif isinstance(value, (str, bytes)):
        # Also fine - might want to do checking on this for encoding etc?
        pass
    elif isinstance(value, list):
        raise BadSchemaError("Error at {} - expected a dict, str, or !!binary".format(path))

        # invalid = []

        # # Check they're all a list of 2-tuples
        # for p in value:
        #     if not isinstance(p, list):
        #         invalid += p
        #     elif len(p) != 2:
        #         invalid += p

        # if invalid:
        #     raise BadSchemaError("Error at {} - when passing a list to the 'data' key, all items must be 2-tuples (invalid values: {})".format(path, invalid))
    else:
        raise BadSchemaError("Error at {} - expected a dict, str, or !!binary".format(path))

    return True


def validate_json_with_extensions(value, rule_obj, path):
    """ Performs the above match, but also matches a dict or a list. This it
    just because it seems like you can't match a dict OR a list in pykwalify
    """
    validate_extensions(value, rule_obj, path)

    if not isinstance(value, (list, dict)):
        raise BadSchemaError("Error at {} - expected a list or dict".format(path))

    def nested_values(d):
        if isinstance(d, dict):
            for v in d.values():
                if isinstance(v, dict):
                    for v_s in v.values():
                        yield v_s
                else:
                    yield v
        else:
            yield d

    if any(isinstance(i, ApproxScalar) for i in nested_values(value)):
        # If this is a request data block
        if not re.search(r"^/stages/\d/(response/body|mqtt_response/json)", path):
            raise BadSchemaError("Error at {} - Cannot use a '!approx' in anything other than an expected http response body or mqtt response json".format(path))

    return True


def check_strict_key(value, rule_obj, path):
    """Make sure the 'strict' key is either a bool or a list"""
    # pylint: disable=unused-argument

    if not isinstance(value, (bool, list)):
        raise BadSchemaError("'strict' has to be either a boolean or a list")
    elif isinstance(value, list):
        if not set(["body", "headers", "redirect_query_params"]) >= set(value):
            raise BadSchemaError("Invalid 'strict' keys passed: {}".format(value))

    return True
