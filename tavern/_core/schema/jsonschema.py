import logging
import re
from collections.abc import Mapping

import jsonschema
from jsonschema import Draft7Validator, ValidationError
from jsonschema.validators import extend

from tavern._core import exceptions
from tavern._core.dict_util import recurse_access_key
from tavern._core.exceptions import BadSchemaError
from tavern._core.loader import (
    AnythingSentinel,
    BoolToken,
    FloatToken,
    IntToken,
    RawStrToken,
    TypeConvertToken,
    TypeSentinel,
)
from tavern._core.pytest.config import has_module
from tavern._core.schema.extensions import (
    check_parametrize_marks,
    check_strict_key,
    retry_variable,
    validate_file_spec,
    validate_grpc_status_is_valid_or_list_of_names,
    validate_http_method,
    validate_json_with_ext,
    validate_request_json,
)
from tavern._core.stage_lines import (
    get_stage_filename,
    get_stage_lines,
    read_relevant_lines,
)

logger: logging.Logger = logging.getLogger(__name__)


def is_str_or_bytes_or_token(checker, instance):
    return Draft7Validator.TYPE_CHECKER.is_type(instance, "string") or isinstance(
        instance, bytes | RawStrToken | AnythingSentinel
    )


def is_number_or_token(checker, instance):
    return Draft7Validator.TYPE_CHECKER.is_type(instance, "number") or isinstance(
        instance, IntToken | FloatToken | AnythingSentinel
    )


def is_integer_or_token(checker, instance):
    return Draft7Validator.TYPE_CHECKER.is_type(instance, "integer") or isinstance(
        instance, IntToken | AnythingSentinel
    )


def is_boolean_or_token(checker, instance):
    return Draft7Validator.TYPE_CHECKER.is_type(instance, "boolean") or isinstance(
        instance, BoolToken | AnythingSentinel
    )


def is_object_or_sentinel(checker, instance):
    return (
        Draft7Validator.TYPE_CHECKER.is_type(instance, "object")
        or isinstance(instance, TypeSentinel | TypeConvertToken)
        or instance is None
    )


def oneOf(validator: Draft7Validator, oneOf, instance, schema):
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
            f"{instance!r} is not valid under any of the given schemas",
            context=all_errors,
        )

    more_valid = [
        s for i, s in subschemas if validator.evolve(schema=s).is_valid(instance)
    ]
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


def verify_jsonschema(to_verify: Mapping, schema: Mapping) -> None:
    """Verify a generic file against a given jsonschema

    Args:
        to_verify: Filename of source tests to check
        schema: Schema to verify against

    Raises:
        BadSchemaError: Schema did not match
    """

    validator = CustomValidator(schema)

    if "grpc" in to_verify and not has_module("grpc"):
        raise exceptions.BadSchemaError(
            "Tried to use grpc connection string, but grpc was not installed. Reinstall Tavern with the grpc extra like `pip install tavern[grpc]`"
        )
    if "mqtt" in to_verify and not has_module("paho.mqtt"):
        raise exceptions.BadSchemaError(
            "Tried to use mqtt connection string, but mqtt was not installed. Reinstall Tavern with the mqtt extra like `pip install tavern[mqtt]`"
        )

    try:
        validator.validate(to_verify)
    except jsonschema.ValidationError as e:
        real_context = []

        # ignore these strings because they're red herrings
        for c in e.context:
            description = c.schema.get("description", "<no description>")
            if description == "Reference to another stage from an included config file":
                continue

            instance = c.instance
            filename = get_stage_filename(instance)
            if filename is None:
                # Depending on what block raised the error, it mightbe difficult to tell what it was, so check the parent too
                instance = e.instance
                filename = get_stage_filename(instance)

            if filename:
                with open(filename, encoding="utf-8") as infile:
                    n_lines = len(infile.readlines())

                first_line, last_line, _ = get_stage_lines(instance)
                first_line = max(first_line - 2, 0)
                last_line = min(last_line + 2, n_lines)

                reg = re.compile(r"^\s*$")

                lines = read_relevant_lines(instance, first_line, last_line)
                lines = [line for line in lines if not reg.match(line.strip())]
                content = "\n".join(list(lines))
                real_context.append(
                    f"""
{c.message}
{filename}: line {first_line}-{last_line}:

{content}
"""
                )
            else:
                real_context.append(
                    f"""
{c.message}

<error: unable to find input file for context>
"""
                )

        logger.debug("original exception from jsonschema: %s", e)

        msg = "\n---\n" + "\n---\n".join([str(i) for i in real_context])
        raise BadSchemaError(msg) from None

    extra_checks = {
        "stages[*].mqtt_publish.json[]": validate_request_json,
        "stages[*].mqtt_response.payload[]": validate_request_json,
        "stages[*].request.json[]": validate_request_json,
        "stages[*].request.data[]": validate_request_json,
        "stages[*].request.params[]": validate_request_json,
        "stages[*].request.headers[]": validate_request_json,
        "stages[*].grpc_response.status[]": validate_grpc_status_is_valid_or_list_of_names,
        "stages[*].request.method[]": validate_http_method,
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
