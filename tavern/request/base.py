from abc import abstractmethod
import logging

logger = logging.getLogger(__name__)


class BaseRequest(object):
    @abstractmethod
    def run(self):
        """Run test"""
