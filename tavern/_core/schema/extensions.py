import os
import re
from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any, Union

from pykwalify.types import is_bool, is_float, is_int

from tavern._core import exceptions
from tavern._core.exceptions import BadSchemaError
from tavern._core.extfunctions import (
    get_pykwalify_logger,
    import_ext_function,
    is_ext_function,
)
from tavern._core.general import valid_http_methods
from tavern._core.loader import (
    ApproxScalar,
    BoolToken,
    FloatToken,
    IntToken,
    TypeConvertToken,
)
from tavern._core.strict_util import StrictLevel

if TYPE_CHECKING:
    from tavern._plugins.grpc.response import GRPCCode


# To extend pykwalify's type validation, extend its internal functions
# These return boolean values
def validate_type_and_token(
    validate_type: Callable[[Any], bool], token: type[TypeConvertToken]
):
    def validate(value):
        return validate_type(value) or isinstance(value, token)

    return validate


is_int_like = validate_type_and_token(is_int, IntToken)
is_float_like = validate_type_and_token(is_float, FloatToken)
is_bool_like = validate_type_and_token(is_bool, BoolToken)


# These plug into the pykwalify extension function API
def validator_like(validate: Callable[[Any], bool], description: str):
    def validator(value, rule_obj, path):
        if validate(value):
            return True
        else:
            err_msg = f"expected '{description}' type at '{path}', got '{value}'"
            raise BadSchemaError(err_msg)

    return validator


int_variable = validator_like(is_int_like, "int-like")
float_variable = validator_like(is_float_like, "float-like")
bool_variable = validator_like(is_bool_like, "bool-like")


def _validate_one_extension(input_value: Mapping) -> None:
    expected_keys = {"function", "extra_args", "extra_kwargs"}
    extra = set(input_value) - expected_keys

    if extra:
        raise BadSchemaError(f"Unexpected keys passed to $ext: {extra}")

    if "function" not in input_value:
        raise BadSchemaError("No function specified for validation")

    try:
        import_ext_function(input_value["function"])
    except Exception as e:
        raise BadSchemaError("Couldn't load {}".format(input_value["function"])) from e

    extra_args = input_value.get("extra_args")
    extra_kwargs = input_value.get("extra_kwargs")

    if extra_args and not isinstance(extra_args, list):
        raise BadSchemaError(f"Expected a list of extra_args, got {type(extra_args)}")

    if extra_kwargs and not isinstance(extra_kwargs, dict):
        raise BadSchemaError(f"Expected a dict of extra_kwargs, got {type(extra_args)}")


def validate_extensions(value, rule_obj, path) -> bool:
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

    if isinstance(value, list):
        for vf in value:
            _validate_one_extension(vf)
    elif isinstance(value, dict):
        _validate_one_extension(value)

    return True


def validate_status_code_is_int_or_list_of_ints(value: Mapping, rule_obj, path) -> bool:
    err_msg = f"status_code has to be an integer or a list of integers (got {value})"

    if not isinstance(value, list) and not is_int_like(value):
        raise BadSchemaError(err_msg)

    if isinstance(value, list):
        if not all(is_int_like(i) for i in value):
            raise BadSchemaError(err_msg)

    return True


def check_usefixtures(value: Mapping, rule_obj, path) -> bool:
    err_msg = "'usefixtures' has to be a list with at least one item"

    if not isinstance(value, list | tuple):
        raise BadSchemaError(err_msg)

    if not value:
        raise BadSchemaError(err_msg)

    return True


def validate_grpc_status_is_valid_or_list_of_names(
    value: "GRPCCode", rule_obj, path
) -> bool:
    """Validate GRPC statuses https://github.com/grpc/grpc/blob/master/doc/statuscodes.md"""
    # pylint: disable=unused-argument
    err_msg = f"status has to be an valid grpc status code, name, or list (got {value})"

    if isinstance(value, str | int):
        if not to_grpc_status(value):
            raise BadSchemaError(err_msg)
    elif isinstance(value, list):
        if not all(to_grpc_status(i) for i in value):
            raise BadSchemaError(err_msg)
    else:
        raise BadSchemaError(err_msg)

    return True


def to_grpc_status(value: Union[str, int]):
    from grpc import StatusCode

    if isinstance(value, str):
        value = value.upper()
        for status in StatusCode:
            if status.name == value:
                return status.name
    elif isinstance(value, int):
        for status in StatusCode:
            if status.value[0] == value:
                return status.name

    return None


def verify_oneof_id_name(value: Mapping, rule_obj, path) -> bool:
    """Checks that if 'name' is not present, 'id' is"""

    if not (name := value.get("name")):
        if name == "":
            raise BadSchemaError("Name cannot be empty")

        if not value.get("id"):
            raise BadSchemaError("If 'name' is not specified, 'id' must be specified")

    return True


def check_parametrize_marks(value, rule_obj, path) -> bool:
    key_or_keys = value["key"]
    vals = value["vals"]

    # At this point we can assume vals is a list - check anyway
    if not (isinstance(vals, list) or is_ext_function(vals)):
        raise BadSchemaError("'vals' should be a list")

    if isinstance(key_or_keys, str):
        # Vals can be anything
        return True
    elif isinstance(key_or_keys, list):
        err_msg = "If 'key' is a list, 'vals' must be a list of lists where each list is the same length as 'key'"

        # Checking for whether the ext function actually returns the correct
        # values has to be deferred until the point where the function is
        # actually called
        if not is_ext_function(vals):
            # broken example:
            # - parametrize:
            #     key:
            #       - edible
            #       - fruit
            #     vals:
            #       a: b
            if not isinstance(vals, list):
                raise BadSchemaError(err_msg)

            # example:
            # - parametrize:
            #     key:
            #       - edible
            #       - fruit
            #     vals:
            #       - [rotten, apple]
            #       - [fresh, orange]
            #       - [unripe, pear]
            for v in vals:
                if not isinstance(v, list):
                    # This catches the case like
                    #
                    # - parametrize:
                    #     key:
                    #       - edible
                    #       - fruit
                    #     vals:
                    #       - fresh
                    #       - orange
                    #
                    # This will parametrize 'edible' as [f, r, e, s, h] which is almost certainly not desired
                    raise BadSchemaError(err_msg)
                if len(v) != len(key_or_keys):
                    # If the 'vals' list has more or less keys
                    raise BadSchemaError(err_msg)

    else:
        raise BadSchemaError("'key' must be a string or a list")

    return True


def validate_data_key(value, rule_obj, path: str) -> bool:
    """Validate the 'data' key in a http request

    From requests docs:

    > data - (optional) Dictionary or list of tuples [(key, value)] (will be
    > form-encoded), bytes, or file-like object to send in the body of the
    > Request.

    We could handle lists of tuples, but it seems entirely pointless to maintain
    compatibility for something which is more verbose and does the same thing
    """

    if isinstance(value, dict):
        # Fine
        pass
    elif isinstance(value, str | bytes):
        # Also fine - might want to do checking on this for encoding etc?
        pass
    elif isinstance(value, list):
        raise BadSchemaError(f"Error at {path} - expected a dict, str, or !!binary")

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
        raise BadSchemaError(f"Error at {path} - expected a dict, str, or !!binary")

    return True


def validate_request_json(value, rule_obj, path) -> bool:
    """Performs the above match, but also matches a dict or a list. This it
    just because it seems like you can't match a dict OR a list in pykwalify
    """

    def nested_values(d):
        if isinstance(d, dict):
            for v in d.values():
                if isinstance(v, dict):
                    yield from v.values()
                else:
                    yield v
        else:
            yield d

    if any(isinstance(i, ApproxScalar) for i in nested_values(value)):
        # If this is a request data block
        if not re.search(r"^/stages/\d/(response/json|mqtt_response/json)", path):
            raise BadSchemaError(
                f"Error at {path} - Cannot use a '!approx' in anything other than an expected http response body or mqtt response json"
            )

    return True


def validate_json_with_ext(value, rule_obj, path) -> bool:
    """Validate json with extensions"""
    validate_request_json(value, rule_obj, path)

    if isinstance(value, dict):
        maybe_ext_val = value.get("$ext", None)
        if isinstance(maybe_ext_val, dict):
            validate_extensions(maybe_ext_val, rule_obj, path)
        elif maybe_ext_val is not None:
            raise BadSchemaError(f"Unexpected $ext key in block at {path}")

    return True


def check_strict_key(value: Union[list, bool], rule_obj, path) -> bool:
    """Make sure the 'strict' key is either a bool or a list"""

    if not isinstance(value, list) and not is_bool_like(value):
        raise BadSchemaError("'strict' has to be either a boolean or a list")
    elif isinstance(value, list):
        try:
            # Reuse validation here
            StrictLevel.from_options(value)
        except exceptions.InvalidConfigurationException as e:
            raise BadSchemaError from e

    # Might be a bool as well, in which case it's processed further down the line - no validation required

    return True


def validate_timeout_tuple_or_float(value: Union[list, tuple], rule_obj, path) -> bool:
    """Make sure timeout is a float/int or a tuple of floats/ints"""

    err_msg = f"'timeout' must be either a float/int or a 2-tuple of floats/ints - got '{value}' (type {type(value)})"
    logger = get_pykwalify_logger("tavern.schemas.extensions")

    def check_is_timeout_val(v):
        if v is True or v is False or not (is_float_like(v) or is_int_like(v)):
            logger.debug("'timeout' value not a float/int")
            raise BadSchemaError(err_msg)

    if isinstance(value, list | tuple):
        if len(value) != 2:
            raise BadSchemaError(err_msg)
        for v in value:
            check_is_timeout_val(v)
    else:
        check_is_timeout_val(value)

    return True


def validate_verify_bool_or_str(value: Union[bool, str], rule_obj, path) -> bool:
    """Make sure the 'verify' key is either a bool or a str"""

    if not isinstance(value, bool | str) and not is_bool_like(value):
        raise BadSchemaError(
            "'verify' has to be either a boolean or the path to a CA_BUNDLE file or directory with certificates of trusted CAs"
        )

    return True


def validate_cert_tuple_or_str(value, rule_obj, path) -> bool:
    """Make sure the 'cert' key is either a str or tuple"""

    err_msg = (
        "The 'cert' key must be the path to a single file (containing the private key and the certificate) "
        "or as a tuple of both files"
    )

    if not isinstance(value, str | tuple | list):
        raise BadSchemaError(err_msg)

    if isinstance(value, list | tuple):
        if len(value) != 2:
            raise BadSchemaError(err_msg)
        elif not all(isinstance(i, str) for i in value):
            raise BadSchemaError(err_msg)

    return True


def validate_file_spec(value: dict, rule_obj, path) -> bool:
    """Validate file upload arguments"""

    logger = get_pykwalify_logger("tavern.schema.extensions")

    if not isinstance(value, dict):
        raise BadSchemaError(
            f"File specification must be a mapping of file names to file specs, got {value}"
        )

    if value.get("file_path"):
        # If the file spec was a list, this function will be called for each item. Just call this
        # function recursively to check each item.
        return validate_file_spec({"file": value}, rule_obj, path)

    for _, filespec in value.items():
        if isinstance(filespec, str):
            file_path = filespec
        elif isinstance(filespec, dict):
            valid = {"file_path", "content_type", "content_encoding", "form_field_name"}
            extra = set(filespec.keys()) - valid
            if extra:
                raise BadSchemaError(
                    f"Invalid extra keys passed to file upload block: {extra}"
                )

            try:
                file_path = filespec["file_path"]
            except KeyError as e:
                raise BadSchemaError(
                    "When using 'long form' file uplaod spec, the file_path must be present"
                ) from e
        else:
            raise BadSchemaError(
                "File specification must be a file path or a dictionary"
            )

        if not os.path.exists(file_path):
            if re.search(".*{.+}.*", file_path):
                logger.debug(
                    "Could not find file path, but it might be a format variable, so continuing"
                )
            else:
                raise BadSchemaError(
                    f"Path to file to upload '{file_path}' was not found"
                )

    return True


def raise_body_error(value, rule_obj, path):
    """Raise an error about the deprecated 'body' key"""

    msg = "The 'body' key has been replaced with 'json' in 1.0 to make it more in line with other blocks. see https://github.com/taverntesting/tavern/issues/495 for details."
    raise BadSchemaError(msg)


def retry_variable(value: int, rule_obj, path) -> bool:
    """Check retry variables"""

    int_variable(value, rule_obj, path)

    if isinstance(value, int):
        if value < 0:
            raise BadSchemaError("max_retries must be greater than 0")

    return True


def validate_http_method(value: str, rule_obj, path) -> bool:
    """Check http method"""

    if not isinstance(value, str):
        raise BadSchemaError("HTTP method should be a string")

    if value not in valid_http_methods:
        logger = get_pykwalify_logger("tavern.schemas.extensions")
        logger.debug(
            "Givern HTTP method '%s' was not one of %s - assuming it will be templated",
            value,
            valid_http_methods,
        )

    return True
