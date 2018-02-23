from abc import abstractmethod


class BaseRequest(object):

    @abstractmethod
    def run(self):
        """Run test"""
