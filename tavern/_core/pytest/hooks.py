import re

import pytest

from tavern._core import exceptions

from .util import add_ini_options, add_parser_options, get_option_generic


def pytest_addoption(parser):
    add_parser_options(parser.addoption, with_defaults=False)
    add_ini_options(parser)


def pytest_collect_file(parent, path):
    """On collecting files, get any files that end in .tavern.yaml or .tavern.yml as tavern
    test files
    """

    if int(pytest.__version__.split(".")[0]) < 5:
        raise exceptions.TavernException("Only pytest >=5 is supported")

    pattern = get_option_generic(
        parent.config, "tavern-file-path-regex", r".+\.tavern\.ya?ml$"
    )

    if isinstance(pattern, list):
        if len(pattern) != 1:
            raise exceptions.InvalidConfigurationException(
                "tavern-file-path-regex must have exactly one option"
            )
        pattern = pattern[0]

    try:
        compiled = re.compile(pattern)
    except Exception as e:  # pylint: disable=broad-except
        raise exceptions.InvalidConfigurationException(e) from e

    match_tavern_file = compiled.search

    from .file import YamlFile

    if match_tavern_file(path.strpath):
        return YamlFile.from_parent(parent, fspath=path)

    return None


def pytest_addhooks(pluginmanager):
    """Add our custom tavern hooks"""
    from . import newhooks  # pylint: disable=import-outside-toplevel

    pluginmanager.add_hookspecs(newhooks)
