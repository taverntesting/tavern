import logging

import jsonschema
from jsonschema import Draft7Validator, ValidationError
from jsonschema.validators import extend

from tavern.schemas.extensions import (
    check_parametrize_marks,
    check_strict_key,
    retry_variable,
    validate_file_spec,
    validate_json_with_ext,
    validate_request_json,
)
from tavern.util.dict_util import recurse_access_key
from tavern.util.exceptions import BadSchemaError
from tavern.util.loader import (
    AnythingSentinel,
    BoolToken,
    FloatToken,
    IntToken,
    RawStrToken,
    TypeConvertToken,
    TypeSentinel,
)

logger = logging.getLogger(__name__)


def is_str_or_bytes_or_token(checker, instance):  # pylint: disable=unused-argument
    return Draft7Validator.TYPE_CHECKER.is_type(instance, "string") or isinstance(
        instance, (bytes, RawStrToken, AnythingSentinel)
    )


def is_number_or_token(checker, instance):  # pylint: disable=unused-argument
    return Draft7Validator.TYPE_CHECKER.is_type(instance, "number") or isinstance(
        instance, (IntToken, FloatToken, AnythingSentinel)
    )


def is_integer_or_token(checker, instance):  # pylint: disable=unused-argument
    return Draft7Validator.TYPE_CHECKER.is_type(instance, "integer") or isinstance(
        instance, (IntToken, AnythingSentinel)
    )


def is_boolean_or_token(checker, instance):  # pylint: disable=unused-argument
    return Draft7Validator.TYPE_CHECKER.is_type(instance, "boolean") or isinstance(
        instance, (BoolToken, AnythingSentinel)
    )


def is_object_or_sentinel(checker, instance):  # pylint: disable=unused-argument
    return (
        Draft7Validator.TYPE_CHECKER.is_type(instance, "object")
        or isinstance(instance, (TypeSentinel, TypeConvertToken))
        or instance is None
    )


def oneOf(
    validator, oneOf, instance, schema
):  # pylint: disable=redefined-outer-name,unused-argument
    """Patched version of 'oneof' that does not complain if something is matched by multiple branches"""
    subschemas = enumerate(oneOf)
    all_errors = []
    for index, subschema in subschemas:
        errs = list(validator.descend(instance, subschema, schema_path=index))
        if not errs:
            first_valid = subschema
            break
        all_errors.extend(errs)
    else:
        yield ValidationError(
            "%r is not valid under any of the given schemas" % (instance,),
            context=all_errors,
        )

    more_valid = [s for i, s in subschemas if validator.is_valid(instance, s)]
    if more_valid:
        more_valid.append(first_valid)
        reprs = ", ".join(repr(schema) for schema in more_valid)
        logger.debug("%r is valid under each of %s", instance, reprs)


CustomValidator = extend(
    Draft7Validator,
    type_checker=Draft7Validator.TYPE_CHECKER.redefine("object", is_object_or_sentinel)
    .redefine("string", is_str_or_bytes_or_token)
    .redefine("boolean", is_boolean_or_token)
    .redefine("integer", is_integer_or_token)
    .redefine("number", is_number_or_token),
    validators={
        "oneOf": oneOf,
    },
)


def verify_jsonschema(to_verify, schema):
    """Verify a generic file against a given jsonschema

    Args:
        to_verify (dict): Filename of source tests to check
        schema (dict): Schema to verify against

    Raises:
        BadSchemaError: Schema did not match
    """

    validator = CustomValidator(schema)

    try:
        validator.validate(to_verify)
    except jsonschema.ValidationError as e:
        logger.error("e.message: %s", e.message)
        logger.error("e.context: %s", e.context)
        logger.error("e.cause: %s", e.cause)
        logger.error("e.instance: %s", e.instance)
        logger.error("e.path: %s", e.path)
        logger.error("e.schema: %s", e.schema)
        logger.error("e.schema_path: %s", e.schema_path)
        logger.error("e.validator: %s", e.validator)
        logger.error("e.validator_value: %s", e.validator_value)
        logger.exception("Error validating %s", to_verify)

        real_context = []
        ignore_strings = [
            "'type' is a required property",
            "'id' is a required property",
        ]

        # ignore these strings because they're red herrings
        for c in e.context:
            if not any(i in str(c) for i in ignore_strings):
                real_context.append(c)

        msg = "err:\n---\n" + """"\n---\n""".join([str(i) for i in real_context])
        raise BadSchemaError(msg) from e

    extra_checks = {
        "stages[*].mqtt_publish.json[]": validate_request_json,
        "stages[*].mqtt_response.payload[]": validate_request_json,
        "stages[*].request.json[]": validate_request_json,
        "stages[*].request.data[]": validate_request_json,
        "stages[*].request.params[]": validate_request_json,
        "stages[*].request.headers[]": validate_request_json,
        "stages[*].request.save[]": validate_json_with_ext,
        "stages[*].request.files[]": validate_file_spec,
        "marks[*].parametrize[]": check_parametrize_marks,
        "stages[*].response.strict[]": validate_json_with_ext,
        "stages[*].max_retries[]": retry_variable,
        "strict": check_strict_key,
    }

    for path, func in extra_checks.items():
        data = recurse_access_key(to_verify, path)
        if data:
            if path.endswith("[]"):
                if not isinstance(data, list):
                    raise BadSchemaError

                for element in data:
                    func(element, None, path)
            else:
                func(data, None, path)
