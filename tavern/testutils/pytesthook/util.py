from functools import lru_cache
import logging

from tavern.testutils.pytesthook.config import TavernInternalConfig, TestConfig
from tavern.util.dict_util import format_keys, get_tavern_box
from tavern.util.general import load_global_config
from tavern.util.strict_util import StrictLevel

logger = logging.getLogger(__name__)


def add_parser_options(parser_addoption, with_defaults=True):
    """Add argparse options

    This is shared between the CLI and pytest (for now)

    See also testutils.pytesthook.hooks.pytest_addoption
    """
    parser_addoption(
        "--tavern-global-cfg",
        help="One or more global configuration files to include in every test",
        nargs="+",
    )
    parser_addoption(
        "--tavern-http-backend",
        help="Which http backend to use",
        default="requests" if with_defaults else None,
    )
    parser_addoption(
        "--tavern-mqtt-backend",
        help="Which mqtt backend to use",
        default="paho-mqtt" if with_defaults else None,
    )
    parser_addoption(
        "--tavern-strict",
        help="Default response matching strictness",
        default=None,
        nargs="+",
        choices=["json", "headers", "redirect_query_params"],
    )
    parser_addoption(
        "--tavern-use-default-traceback",
        help="Use normal python-style traceback",
        default=False,
        action="store_true",
    )
    parser_addoption(
        "--tavern-always-follow-redirects",
        help="Always follow HTTP redirects",
        default=False,
        action="store_true",
    )
    parser_addoption(
        "--tavern-file-path-regex",
        help="Regex to search for Tavern YAML test files",
        default=r".+\.tavern\.ya?ml$",
        action="store",
        nargs=1,
    )


def add_ini_options(parser):
    """Add an option to pass in a global config file for tavern

    See also testutils.pytesthook.util.add_parser_options
    """
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
        "tavern-use-default-traceback",
        help="Use normal python-style traceback",
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
        type="args",
    )


@lru_cache()
def load_global_cfg(pytest_config):
    """Load globally included config files from cmdline/cfg file arguments

    Args:
        pytest_config (pytest.Config): Pytest config object

    Returns:
        dict: variables/stages/etc from global config files

    Raises:
        exceptions.UnexpectedKeysError: Invalid settings in one or more config
            files detected
    """
    # Load ini first
    ini_global_cfg_paths = pytest_config.getini("tavern-global-cfg") or []
    # THEN load command line, to allow overwriting of values
    cmdline_global_cfg_paths = pytest_config.getoption("tavern_global_cfg") or []

    all_paths = ini_global_cfg_paths + cmdline_global_cfg_paths
    global_cfg_dict = load_global_config(all_paths)

    try:
        loaded_variables = global_cfg_dict["variables"]
    except KeyError:
        logger.debug("Nothing to format in global config files")
        variables = {}
    else:
        tavern_box = get_tavern_box()
        variables = format_keys(loaded_variables, tavern_box)

    global_cfg = TestConfig(
        variables=variables,
        strict=_load_global_strictness(pytest_config),
        follow_redirects=_load_global_follow_redirects(pytest_config),
        tavern_internal=TavernInternalConfig(
            pytest_hook_caller=pytest_config.hook,
            backends=_load_global_backends(pytest_config),
        ),
        stages=global_cfg_dict.get("stages", []),
    )

    return global_cfg


def _load_global_backends(pytest_config):
    """Load which backend should be used"""
    backend_settings = {}

    backends = ["http", "mqtt"]
    for b in backends:
        backend_settings[b] = get_option_generic(
            pytest_config, "tavern-{}-backend".format(b), None
        )

    return backend_settings


def _load_global_strictness(pytest_config):
    """Load the global 'strictness' setting"""

    options = get_option_generic(pytest_config, "tavern-strict", [])

    return StrictLevel.from_options(options)


def _load_global_follow_redirects(pytest_config):
    """Load the global 'follow redirects' setting"""
    return get_option_generic(pytest_config, "tavern-always-follow-redirects", False)


def get_option_generic(pytest_config, flag, default):
    """Get a configuration option or return the default

    Priority order is cmdline, then ini, then default"""
    cli_flag = flag.replace("-", "_")
    ini_flag = flag

    # Lowest priority
    use = default

    # Middle priority
    if pytest_config.getini(ini_flag) is not None:
        use = pytest_config.getini(ini_flag)

    # Top priority
    if pytest_config.getoption(cli_flag) is not None:
        use = pytest_config.getoption(cli_flag)

    return use
