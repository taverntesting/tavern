import logging
import pathlib
from collections.abc import Iterable
from os.path import abspath, dirname, join
from typing import Any, Optional, Union

import box
import yaml

from tavern._core import exceptions
from tavern._core.pytest.config import TestConfig
from tavern.request import BaseRequest
from tavern.response import BaseResponse


class Session:
    """No-op session, but must implement the context manager protocol"""
    def __enter__(self):
        pass

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class Request(BaseRequest):
    """Touches a file when the 'request' is made"""
    def __init__(
        self, session: Any, rspec: dict, test_block_config: TestConfig
    ) -> None:
        self.session = session

        self._request_vars = rspec

    @property
    def request_vars(self) -> box.Box:
        return self._request_vars

    def run(self):
        pathlib.Path(self._request_vars["filename"]).touch()


class Response(BaseResponse):
    def verify(self, response):
        if not pathlib.Path(self.expected["filename"]).exists():
            raise exceptions.BadSchemaError(
                f"Expected file '{self.expected['filename']}' does not exist"
            )

        return {}

    def __init__(
        self,
        client,
        name: str,
        expected: TestConfig,
        test_block_config: TestConfig,
    ) -> None:
        super().__init__(name, expected, test_block_config)


logger: logging.Logger = logging.getLogger(__name__)

session_type = Session

request_type = Request
request_block_name = "touch_file"


verifier_type = Response
response_block_name = "file_exists"


def get_expected_from_request(
    response_block: Union[dict, Iterable[dict]],
    test_block_config: TestConfig,
    session: Session,
) -> Optional[dict]:
    return response_block


schema_path: str = join(abspath(dirname(__file__)), "jsonschema.yaml")
with open(schema_path, encoding="utf-8") as schema_file:
    schema = yaml.load(schema_file, Loader=yaml.SafeLoader)
