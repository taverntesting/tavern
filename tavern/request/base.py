from abc import abstractmethod

from box import Box


class BaseRequest(object):

    @abstractmethod
    def run(self):
        """Run test"""

    @property
    def request_vars(self):
        return Box(self._request_args)
