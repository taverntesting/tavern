from abc import abstractmethod
import logging

import box

logger = logging.getLogger(__name__)


class BaseRequest:
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
