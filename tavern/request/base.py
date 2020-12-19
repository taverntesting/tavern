from abc import abstractmethod
import logging

logger = logging.getLogger(__name__)


class BaseRequest(object):
    @property
    @abstractmethod
    def request_vars(self):
        """
        Variables used in the request

        What is contained in the return value will change depending on the type of request

        Returns:
            box.Box: box of request vars
        """

    @abstractmethod
    def run(self):
        """Run test"""
