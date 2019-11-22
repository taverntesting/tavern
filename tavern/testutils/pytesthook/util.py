import logging
import os

from box import Box

from tavern.util import exceptions
from tavern.util.dict_util import format_keys
from tavern.util.general import load_global_config

try:
    from functools import lru_cache
except ImportError:
    from backports.functools_lru_cache import lru_cache

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
        choices=["body", "headers", "redirect_query_params"],
    )
    parser_addoption(
        "--tavern-beta-new-traceback",
        help="Use new traceback style (beta)",
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
    global_cfg = load_global_config(all_paths)

    try:
        loaded_variables = global_cfg["variables"]
    except KeyError:
        logger.debug("Nothing to format in global config files")
    else:
        tavern_box = Box({"tavern": {"env_vars": dict(os.environ)}})

        global_cfg["variables"] = format_keys(loaded_variables, tavern_box)

    # Can be overridden in tests
    global_cfg["strict"] = _load_global_strictness(pytest_config)
    global_cfg["follow_redirects"] = _load_global_follow_redirects(pytest_config)
    global_cfg["backends"] = _load_global_backends(pytest_config)

    logger.debug("Global config: %s", global_cfg)

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

    strict = get_option_generic(pytest_config, "tavern-strict", [])

    if isinstance(strict, list):
        valid_keys = ["body", "headers", "redirect_query_params"]
        if any(i not in valid_keys for i in strict):
            msg = "Invalid values for 'strict' given - expected one of {}, got {}".format(
                valid_keys, strict
            )
            raise exceptions.InvalidConfigurationException(msg)

    return strict


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

    if pytest_config.getini(ini_flag) is not None:
        # Middle priority
        use = pytest_config.getini(ini_flag)

    if pytest_config.getoption(cli_flag) is not None:
        # Top priority
        use = pytest_config.getoption(cli_flag)

    return use
