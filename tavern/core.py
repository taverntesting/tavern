import os
from contextlib import ExitStack
from typing import Union

import pytest
from _pytest.config import ExitCode

from tavern._core import exceptions
from tavern._core.schema.files import wrapfile


def _get_or_wrap_global_cfg(
    stack: ExitStack, tavern_global_cfg: Union[dict, str]
) -> str:
    """
    Try to parse global configuration from given argument.

    Args:
        stack: context stack for wrapping file if a dictionary is given
        tavern_global_cfg: path to a file or a dictionary with configuration.

    Returns:
        path to global config file

    Raises:
        InvalidSettingsError: If global config was not of the right type or a given path
            does not exist
    """

    if isinstance(tavern_global_cfg, str):
        if not os.path.exists(tavern_global_cfg):
            raise exceptions.InvalidSettingsError(
                f"global config file '{tavern_global_cfg}' does not exist"
            )
        global_filename = tavern_global_cfg
    elif isinstance(tavern_global_cfg, dict):
        global_filename = stack.enter_context(wrapfile(tavern_global_cfg))
    else:
        raise exceptions.InvalidSettingsError(
            f"Invalid format for global settings - must be dict or path to settings file, was {type(tavern_global_cfg)}"
        )

    return global_filename


def run(  # type:ignore
    in_file: str,
    tavern_global_cfg: Union[dict, str, None] = None,
    tavern_mqtt_backend: Union[str, None] = None,
    tavern_http_backend: Union[str, None] = None,
    tavern_grpc_backend: Union[str, None] = None,
    tavern_strict: Union[bool, None] = None,
    pytest_args: Union[list, None] = None,
) -> Union[ExitCode, int]:
    """Run all tests contained in a file using pytest.main()

    Args:
        in_file: file to run tests on
        tavern_global_cfg: Extra global config
        tavern_mqtt_backend: name of MQTT plugin to use. If not
            specified, uses tavern-mqtt
        tavern_http_backend: name of HTTP plugin to use. If not
            specified, use tavern-http
        tavern_grpc_backend: name of GRPC plugin to use. If not
            specified, use tavern-grpc
        tavern_strict: Strictness of checking for responses.
            See documentation for details
        pytest_args: List of extra arguments to pass directly
            to Pytest as if they were command line arguments

    Returns:
        Whether ALL tests passed or not
    """

    pytest_args = pytest_args or []
    pytest_args += [in_file]

    if tavern_mqtt_backend:
        pytest_args += ["--tavern-mqtt-backend", tavern_mqtt_backend]
    if tavern_http_backend:
        pytest_args += ["--tavern-http-backend", tavern_http_backend]
    if tavern_grpc_backend:
        pytest_args += ["--tavern-grpc-backend", tavern_grpc_backend]
    if tavern_strict:
        pytest_args += ["--tavern-strict", tavern_strict]

    with ExitStack() as stack:
        if tavern_global_cfg:
            global_filename = _get_or_wrap_global_cfg(stack, tavern_global_cfg)
            pytest_args += ["--tavern-global-cfg", global_filename]
        return pytest.main(args=pytest_args)
