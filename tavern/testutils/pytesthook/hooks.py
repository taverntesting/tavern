import re

from .file import YamlFile
from .util import add_parser_options


def pytest_addoption(parser):
    """Add an option to pass in a global config file for tavern
    """
    add_parser_options(parser.addoption, with_defaults=False)

    parser.addini(
        "tavern-global-cfg",
        help="One or more global configuration files to include in every test",
        type="linelist",
        default=[],
    )
    parser.addini(
        "tavern-http-backend", help="Which http backend to use", default="requests"
    )
    parser.addini(
        "tavern-mqtt-backend", help="Which mqtt backend to use", default="paho-mqtt"
    )
    parser.addini(
        "tavern-strict",
        help="Default response matching strictness",
        type="args",
        default=None,
    )
    parser.addini(
        "tavern-beta-new-traceback",
        help="Use new traceback style (beta)",
        type="bool",
        default=False,
    )


def pytest_collect_file(parent, path):
    """On collecting files, get any files that end in .tavern.yaml or .tavern.yml as tavern
    test files

    Todo:
        Change this to .tyaml or something?
    """
    match_tavern_file = re.compile(r".+\.tavern\.ya?ml$").match

    if path.basename.startswith("test") and match_tavern_file(path.strpath):
        return YamlFile(path, parent)

    return None
