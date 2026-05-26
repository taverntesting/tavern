import contextlib
import logging
from collections.abc import Mapping
from typing import Any, Optional, Protocol

from requests.status_codes import _codes  # type:ignore

from tavern._core import exceptions
from tavern._core.dict_util import deep_dict_merge
from tavern._core.pytest.config import TestConfig
from tavern._core.schema.openapi import (
    convert_openapi_schema_to_tavern_format,
    get_schema_from_ref,
    load_openapi_schema,
    validate_response_with_openapi,
)
from tavern._core.strict_util import StrictOption, StrictSetting
from tavern.response import BaseResponse

logger: logging.Logger = logging.getLogger(__name__)


class ResponseLike(Protocol):
    """Protocol for response-like objects"""

    headers: Mapping[str, str]

    @property
    def text(self) -> str: ...

    def json(self) -> Any: ...


class CommonResponse(BaseResponse):
    """Common response verification functionality shared by REST and GraphQL"""

    def __init__(
        self,
        session,
        name: str,
        expected: dict[str, Any],
        test_block_config: TestConfig,
        default_status_code: int = 200,
    ) -> None:
        defaults = {"status_code": default_status_code}
        super().__init__(name, deep_dict_merge(defaults, expected), test_block_config)

        def check_code(code: int) -> None:
            if int(code) not in _codes:
                logger.warning("Unexpected status code '%s'", code)

        in_file = self.expected["status_code"]
        try:
            if isinstance(in_file, list):
                for code_ in in_file:
                    check_code(code_)
            else:
                check_code(in_file)
        except TypeError as e:
            raise exceptions.BadSchemaError("Invalid code") from e

    def __str__(self) -> str:
        if self.response:
            return self.response.text.strip()
        else:
            return "<Not run yet>"

    def _verbose_log_response(self, response: ResponseLike) -> None:
        """Verbosely log the response object, with query params etc."""

        logger.info("Response: '%s'", response)

        def log_dict_block(block, name):
            if block:
                to_log = name + ":"

                if isinstance(block, list):
                    for v in block:
                        to_log += f"\n  - {v}"
                elif isinstance(block, dict):
                    for k, v in block.items():
                        to_log += f"\n  {k}: {v}"
                else:
                    to_log += f"\n {block}"
                logger.debug(to_log)

        if hasattr(response, "headers"):
            log_dict_block(response.headers, "Headers")

        with contextlib.suppress(ValueError):
            log_dict_block(response.json(), "Body")

    def _validate_block(
        self, blockname: str, block: Mapping, read_from: Optional[dict] = None
    ) -> None:
        """Validate a block of the response

        Args:
            blockname: which part of the response is being checked
            block: The actual part being checked
            read_from: The block to read from, or self.expected if not specified
        """
        if read_from is None:
            read_from = self.expected

        try:
            expected_block = read_from[blockname]
        except KeyError:
            expected_block = None

        # Handle OpenAPI schema validation
        if blockname == "json" and expected_block and isinstance(expected_block, dict):
            with_openapi = expected_block.get("with_openapi")
            if with_openapi:
                self._validate_openapi_schema(expected_block, block)
                return

        if isinstance(expected_block, dict):
            if expected_block.pop("$ext", None):
                raise exceptions.MisplacedExtBlockException(
                    blockname,
                )

        if blockname == "headers" and expected_block is not None:
            # Special case for headers. These need to be checked in a case
            # insensitive manner
            block = {i.lower(): j for i, j in block.items()}
            expected_block = {i.lower(): j for i, j in expected_block.items()}

        logger.debug("Validating response '%s' against %s", blockname, expected_block)

        test_strictness = self.test_block_config.strict
        if blockname == "data":
            block_strictness = test_strictness.option_for("json")
        else:
            block_strictness = test_strictness.option_for(blockname)

        self.recurse_check_key_match(expected_block, block, blockname, block_strictness)

    def _validate_openapi_schema(
        self, expected_block: dict, block: Mapping
    ) -> None:
        """Validate response block against an OpenAPI schema

        Args:
            expected_block: The expected block containing 'with_openapi' key
            block: The actual response block to validate

        Raises:
            BadSchemaError: If validation fails
        """
        with_openapi = expected_block.get("with_openapi")

        if not isinstance(with_openapi, dict):
            raise exceptions.BadSchemaError(
                "'with_openapi' must be a dictionary with 'path' and 'schema' keys"
            )

        schema_path = with_openapi.get("path")
        schema_ref = with_openapi.get("schema")

        if not schema_path:
            raise exceptions.BadSchemaError(
                "'with_openapi' must have a 'path' key specifying the OpenAPI schema file"
            )

        if not schema_ref:
            raise exceptions.BadSchemaError(
                "'with_openapi' must have a 'schema' key specifying the JSON reference "
                "to the schema (e.g., '#/components/schemas/User')"
            )

        try:
            # First validate using jsonschema - this checks types and required fields
            validate_response_with_openapi(block, schema_path, schema_ref)

            # Then convert to Tavern format and do recursive key matching
            # for any additional specific value checks
            openapi_schema = load_openapi_schema(schema_path)
            target_schema = get_schema_from_ref(openapi_schema, schema_ref)
            tavern_format = convert_openapi_schema_to_tavern_format(target_schema)

            # Extract additional json validation keys (everything except 'with_openapi')
            additional_json = {
                k: v for k, v in expected_block.items() if k != "with_openapi"
            }

            if additional_json:
                # Merge the OpenAPI-derived format with any additional json validation
                # Additional json takes precedence over the OpenAPI-derived format
                tavern_format = deep_dict_merge(tavern_format, additional_json)

            # Perform recursive key matching
            # We use False (non-strict) mode because:
            # 1. jsonschema already validated the structure (types, required fields)
            # 2. We don't want to complain about extra keys that are optional in the schema
            # 3. We only want to check specific values if additional json validation was provided
            logger.debug(
                "Validating response against OpenAPI schema '%s' from '%s'",
                schema_ref,
                schema_path,
            )

            # If there's additional json validation, do the recursive check
            # Otherwise skip it since jsonschema already validated everything
            if additional_json:
                # Use non-strict mode (False) to allow extra keys in response
                # The jsonschema validation already checked the structure
                self.recurse_check_key_match(
                    tavern_format, block, "json", False
                )
            else:
                # No additional validation needed - jsonschema already validated everything
                logger.debug(
                    "OpenAPI schema validation passed - no additional checks needed"
                )

        except exceptions.BadSchemaError:
            raise
        except Exception as e:
            raise exceptions.BadSchemaError(
                f"Error validating against OpenAPI schema: {e}"
            ) from e

    def _common_verify_save(
        self,
        body: Any,
        response: ResponseLike,
    ) -> dict:
        """Common save functionality"""
        saved: dict = {}

        logger.debug(f"Saving response to variables with {body} and {self.expected}")
        if body is not None:
            saved.update(self.maybe_get_save_values_from_save_block("json", body))

        saved.update(self.maybe_get_save_values_from_ext(response, self.expected))

        return saved
