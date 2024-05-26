import logging
from abc import abstractmethod
from typing import Any

import box

from tavern._core.pytest.config import TestConfig

logger: logging.Logger = logging.getLogger(__name__)


class BaseRequest:
    @abstractmethod
    def __init__(
        self, session: Any, rspec: dict, test_block_config: TestConfig
    ) -> None: ...

    @property
    @abstractmethod
    def request_vars(self) -> box.Box:
        """
        Variables used in the request

        What is contained in the return value will change depending on the type of request

        Returns:
            box.Box: box of request vars
        """

    @abstractmethod
    def run(self):
        """Run test"""
