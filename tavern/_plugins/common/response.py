import contextlib
import logging
from collections.abc import Mapping
from typing import Any, Protocol

from requests.status_codes import _codes  # type:ignore

from tavern._core import exceptions
from tavern._core.dict_util import deep_dict_merge
from tavern._core.pytest.config import TestConfig
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

        log_dict_block(response.headers, "Headers")

        with contextlib.suppress(ValueError):
            log_dict_block(response.json(), "Body")

    def _validate_block(self, blockname: str, block: Mapping) -> None:
        """Validate a block of the response

        Args:
            blockname: which part of the response is being checked
            block: The actual part being checked
        """
        try:
            expected_block = self.expected[blockname]
        except KeyError:
            expected_block = None

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

        logger.debug("Validating response %s against %s", blockname, expected_block)

        test_strictness = self.test_block_config.strict
        block_strictness = test_strictness.option_for(blockname)
        self.recurse_check_key_match(expected_block, block, blockname, block_strictness)

    def _common_verify_setup(self, response: ResponseLike) -> Any | None:
        """Common setup for verify method"""
        self._verbose_log_response(response)

        self.response = response

        # Get things to use from the response
        try:
            body = response.json()
        except ValueError:
            body = None

        return body

    def _common_verify_save(
        self,
        body: Any,
        response: ResponseLike,
    ) -> dict:
        """Common save functionality"""
        saved: dict = {}

        if body is not None:
            saved.update(self.maybe_get_save_values_from_save_block("json", body))

        saved.update(
            self.maybe_get_save_values_from_save_block("headers", response.headers)
        )

        saved.update(self.maybe_get_save_values_from_ext(response, self.expected))

        return saved
