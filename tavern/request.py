import abc
from typing import Any

import box

from tavern._core.pytest.config import TestConfig


class BaseRequest(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def __init__(
        self, session: Any, rspec: dict, test_block_config: TestConfig
    ) -> None: ...

    @property
    @abc.abstractmethod
    def request_vars(self) -> box.Box:
        """
        Variables used in the request

        What is contained in the return value will change depending on the type of request

        Returns:
            box.Box: box of request vars
        """

    @abc.abstractmethod
    def run(self):
        """Run test"""
