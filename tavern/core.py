from contextlib import ExitStack
import os

import pytest

from tavern._core import exceptions
from tavern._core.schema.files import wrapfile


def _get_or_wrap_global_cfg(stack, tavern_global_cfg):
    """
    Try to parse global configuration from given argument.

    Args:
        stack (ExitStack): context stack for wrapping file if a dictionary is given
        tavern_global_cfg (dict, str): Dictionary or string. It should be a
            path to a file or a dictionary with configuration.

    Returns:
        str: path to global config file

    Raises:
        InvalidSettingsError: If global config was not of the right type or a given path
            does not exist

    Todo:
        Once python 2 is dropped, allow this to take a 'path like object'
    """
    if isinstance(tavern_global_cfg, str):
        if not os.path.exists(tavern_global_cfg):
            raise exceptions.InvalidSettingsError(
                "global config file '{}' does not exist".format(tavern_global_cfg)
            )
        global_filename = tavern_global_cfg
    elif isinstance(tavern_global_cfg, dict):
        global_filename = stack.enter_context(wrapfile(tavern_global_cfg))
    else:
        raise exceptions.InvalidSettingsError(
            "Invalid format for global settings - must be dict or path to settings file, was {}".format(
                type(tavern_global_cfg)
            )
        )

    return global_filename


def run(
    in_file,
    tavern_global_cfg=None,
    tavern_mqtt_backend=None,
    tavern_http_backend=None,
    tavern_strict=None,
    pytest_args=None,
):  # pylint: disable=too-many-arguments
    """Run all tests contained in a file using pytest.main()

    Args:
        in_file (str): file to run tests on
        tavern_global_cfg (str, dict): Extra global config
        tavern_mqtt_backend (str, optional): name of MQTT plugin to use. If not
            specified, uses tavern-mqtt
        tavern_http_backend (str, optional): name of HTTP plugin to use. If not
            specified, use tavern-http
        tavern_strict (bool, optional): Strictness of checking for responses.
            See documentation for details
        pytest_args (list, optional): List of extra arguments to pass directly
            to Pytest as if they were command line arguments

    Returns:
        bool: Whether ALL tests passed or not
    """

    pytest_args = pytest_args or []
    pytest_args += [in_file]

    if tavern_mqtt_backend:
        pytest_args += ["--tavern-mqtt-backend", tavern_mqtt_backend]
    if tavern_http_backend:
        pytest_args += ["--tavern-http-backend", tavern_http_backend]
    if tavern_strict:
        pytest_args += ["--tavern-strict", tavern_strict]

    with ExitStack() as stack:
        if tavern_global_cfg:
            global_filename = _get_or_wrap_global_cfg(stack, tavern_global_cfg)
            pytest_args += ["--tavern-global-cfg", global_filename]
        return pytest.main(args=pytest_args)
