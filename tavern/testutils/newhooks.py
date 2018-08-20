# pylint: disable=unused-argument

def pytest_tavern_log_response(response):
    """Called when a response is obtained from a server

    Todo:
        This just takes 'response' at the moment, will need to be expanded to
        take the filename and the test name/stage name as well.
    """


def pytest_tavern_before_request(stage):
    """Called before each request"""


def pytest_tavern_after_request(stage):
    """Called after each request"""
