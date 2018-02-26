import logging

import pytest

import yaml

from tavern.core import run_test
from tavern.util.exceptions import TavernException
from tavern.util.loader import IncludeLoader
from tavern.schemas.files import verify_tests


logger = logging.getLogger(__name__)


def pytest_collect_file(parent, path):
    """On collecting files, get any files that end in .tavern.yaml as tavern
    test files

    Todo:
        Change this to .tyaml or something?
    """
    if path.strpath.endswith(".tavern.yaml") and path.basename.startswith("test"):
        return YamlFile(path, parent)

    return None


def pytest_addoption(parser):
    """Add an option to pass in a global config file for tavern
    """
    parser.addoption(
        "--tavern-global-cfg",
        required=False,
        help="Global configuration file to include in every test",
    )


class YamlFile(pytest.File):

    """Custom `File` class that loads each test block as a different test
    """

    def collect(self):
        """Load each document in the given input file into a different test

        Yields:
            YamlItem: Essentially an individual pytest 'test object'
        """
        for test_spec in yaml.load_all(self.fspath.open(), Loader=IncludeLoader):
            if not test_spec:
                logger.warning("Empty document in input file '%s'", self.fspath)
                continue

            yield YamlItem(test_spec["test_name"], self, test_spec, self.fspath)


class YamlItem(pytest.Item):

    """Simple wrapper around new test type that can report errors more
    accurately than the default pytest reporting stuff

    At the time of writing this doesn't print the error very nicely, but it
    should be enough to track down what went wrong

    Attributes:
        path (str): filename that this test came from
        spec (dict): The whole dictionary of the test
    """

    def __init__(self, name, parent, spec, path):
        super(YamlItem, self).__init__(name, parent)
        self.path = path
        self.spec = spec

    def runtest(self):
        verify_tests(self.spec)

        global_cfg = self.config.getoption("tavern_global_cfg") or {}

        if global_cfg:
            with open(global_cfg, "r") as gfileobj:
                contents = yaml.load(gfileobj)
        else:
            contents = {}

        run_test(self.path, self.spec, contents)

    def repr_failure(self, excinfo): # pylint: disable=no-self-use
        """ called when self.runtest() raises an exception.

        Todo:
            This stuff is copied from pytest at the moment - needs a bit of
            modifying so that it shows the yaml and all the reasons the test
            failed rather than a traceback
        """

        if not issubclass(excinfo.type, TavernException):
            return super(YamlItem, self).repr_failure(excinfo)

        return super(YamlItem, self).repr_failure(excinfo)

    def reportinfo(self):
        # pylint: disable=missing-format-attribute
        return self.fspath, 0, "{self.path}::{self.name:s}".format(self=self)
