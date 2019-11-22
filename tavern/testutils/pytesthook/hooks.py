import re

from future.utils import raise_from

from tavern.util import exceptions
from .file import YamlFile
from .util import add_parser_options, get_option_generic


def pytest_addoption(parser):
    """Add an option to pass in a global config file for tavern

    See also testutils.pytesthook.util.add_parser_options
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
    parser.addini(
        "tavern-always-follow-redirects",
        help="Always follow HTTP redirects",
        type="bool",
        default=False,
    )
    parser.addini(
        "tavern-file-path-regex",
        help="Regex to search for Tavern YAML test files",
        default=r".+\.tavern\.ya?ml$",
    )


def pytest_collect_file(parent, path, config):
    """On collecting files, get any files that end in .tavern.yaml or .tavern.yml as tavern
    test files
    """

    pattern = get_option_generic(
        config, "tavern-file-path-regex", r".+\.tavern\.ya?ml$"
    )

    try:
        compiled = re.compile(pattern)
    except Exception as e:
        raise_from(exceptions.InvalidConfigurationException(e), e)

    match_tavern_file = compiled.match

    if path.basename.startswith("test") and match_tavern_file(path.strpath):
        return YamlFile(path, parent)

    return None


def pytest_addhooks(pluginmanager):
    """Add our custom tavern hooks"""
    from . import newhooks

    pluginmanager.add_hookspecs(newhooks)
