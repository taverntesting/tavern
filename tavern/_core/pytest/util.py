import logging
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional, TypeVar, Union

import pytest

from tavern._core.dict_util import format_keys, get_tavern_box
from tavern._core.general import load_global_config
from tavern._core.pytest.config import TavernInternalConfig, TestConfig
from tavern._core.strict_util import StrictLevel

logger: logging.Logger = logging.getLogger(__name__)


def add_parser_options(parser_addoption, with_defaults: bool = True) -> None:
    """Add argparse options

    This is shared between the CLI and pytest (for now)

    See also _core.pytesthook.hooks.pytest_addoption
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
        "--tavern-grpc-backend",
        help="Which grpc backend to use",
        default="grpc" if with_defaults else None,
    )
    parser_addoption(
        "--tavern-strict",
        help="Default response matching strictness",
        default=None,
        nargs="+",
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
    parser_addoption(
        "--tavern-setup-init-logging",
        help="Set up a simple logger for tavern initialisation. Only for internal use and debugging, may be removed in future with no warning.",
        default=False,
        action="store_true",
    )


def add_ini_options(parser: pytest.Parser) -> None:
    """Add an option to pass in a global config file for tavern

    See also _core.pytesthook._core.util.add_parser_options
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
        "tavern-grpc-backend", help="Which grpc backend to use", default="grpc"
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
    parser.addini(
        "tavern-setup-init-logging",
        help="Set up a simple logger for tavern initialisation. Only for internal use and debugging, may be removed in future with no warning.",
        type="bool",
        default=False,
    )


def load_global_cfg(pytest_config: pytest.Config) -> TestConfig:
    return _load_global_cfg(pytest_config).with_new_variables()


@lru_cache
def _load_global_cfg(pytest_config: pytest.Config) -> TestConfig:
    """Load globally included config files from cmdline/cfg file arguments

    Args:
        pytest_config: Pytest config object

    Returns:
        variables/stages/etc from global config files

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

    variables: dict = {}
    try:
        loaded_variables = global_cfg_dict["variables"]
    except KeyError:
        logger.debug("Nothing to format in global config files")
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


def _load_global_backends(pytest_config: pytest.Config) -> dict[str, Any]:
    """Load which backend should be used"""
    return {
        b: get_option_generic(pytest_config, f"tavern-{b}-backend", None)
        for b in TestConfig.backends()
    }


def _load_global_strictness(pytest_config: pytest.Config) -> StrictLevel:
    """Load the global 'strictness' setting"""

    options: list = get_option_generic(pytest_config, "tavern-strict", [])

    return StrictLevel.from_options(options)


def _load_global_follow_redirects(pytest_config: pytest.Config) -> bool:
    """Load the global 'follow redirects' setting"""
    return get_option_generic(pytest_config, "tavern-always-follow-redirects", False)


T = TypeVar("T", bound=Optional[Union[str, list, list[Path], list[str], bool]])


def get_option_generic(
    pytest_config: pytest.Config,
    flag: str,
    default: T,
) -> T:
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
