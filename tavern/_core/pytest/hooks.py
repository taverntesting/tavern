import logging
import logging.config
import os
import pathlib
import re
import typing
from textwrap import dedent
from typing import Optional

if typing.TYPE_CHECKING:
    from .file import YamlFile


import pytest
import yaml

from tavern._core import exceptions

from .util import add_ini_options, add_parser_options, get_option_generic


def pytest_addoption(parser: pytest.Parser) -> None:
    add_parser_options(parser.addoption, with_defaults=False)
    add_ini_options(parser)


def pytest_collect_file(parent, path: os.PathLike) -> Optional["YamlFile"]:
    """On collecting files, get any files that end in .tavern.yaml or .tavern.yml as tavern
    test files
    """

    if int(pytest.__version__.split(".", maxsplit=1)[0]) < 7:
        raise exceptions.TavernException("Only pytest >=7 is supported")

    try:
        setup_initial_logging = get_option_generic(
            parent.config, "tavern-setup-init-logging", False
        )
    except ValueError:
        pass
    else:
        if setup_initial_logging:
            cfg = dedent(
                """
            ---
            version: 1
            formatters:
              default:
                format: "%(asctime)s [%(levelname)s]: (%(name)s:%(lineno)d) %(message)s"
                style: "%"
                datefmt: "%X"

            handlers:
              stderr:
                class : logging.StreamHandler
                level   : DEBUG
                formatter: default
                stream  : ext://sys.stderr

            loggers:
              tavern:
                handlers:
                  - stderr
                level: DEBUG
            """
            )

            settings = yaml.load(cfg, Loader=yaml.SafeLoader)
            logging.config.dictConfig(settings)

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
    except Exception as e:
        raise exceptions.InvalidConfigurationException(e) from e

    match_tavern_file = compiled.search

    from .file import YamlFile

    path = pathlib.Path(path)

    if match_tavern_file(str(path)):
        return YamlFile.from_parent(parent, path=path)

    return None


def pytest_addhooks(pluginmanager) -> None:
    """Add our custom tavern hooks"""
    from . import newhooks

    pluginmanager.add_hookspecs(newhooks)
