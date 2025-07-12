"""
Tavern Core Module

This module provides the core functionality for the Tavern testing framework.
It handles test execution, configuration, and the main testing workflow.

The module contains the central classes and functions that orchestrate
the entire Tavern testing process, from test discovery to execution.
"""

import os
from contextlib import ExitStack
from dataclasses import dataclass
from typing import Union

import pytest
from _pytest.config import ExitCode

from tavern._core import exceptions
from tavern._core.schema.files import wrapfile


@dataclass
class TavernConfig:
    """Configuration object for Tavern test execution."""

    in_file: str
    global_cfg: Union[dict, str, None] = None
    mqtt_backend: Union[str, None] = None
    http_backend: Union[str, None] = None
    grpc_backend: Union[str, None] = None
    strict: Union[bool, None] = None
    pytest_args: Union[list, None] = None


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
            f"Invalid format for global settings - must be dict or path to "
            f"settings file, was {type(tavern_global_cfg)}"
        )

    return global_filename


def run(config: TavernConfig) -> Union[ExitCode, int]:
    """Run all tests contained in a file using pytest.main()

    Args:
        config: TavernConfig object containing all configuration parameters

    Returns:
        Whether ALL tests passed or not
    """

    pytest_args = config.pytest_args or []
    pytest_args += [config.in_file]

    if config.mqtt_backend:
        pytest_args += ["--tavern-mqtt-backend", config.mqtt_backend]
    if config.http_backend:
        pytest_args += ["--tavern-http-backend", config.http_backend]
    if config.grpc_backend:
        pytest_args += ["--tavern-grpc-backend", config.grpc_backend]
    if config.strict:
        pytest_args += ["--tavern-strict", config.strict]

    with ExitStack() as stack:
        if config.global_cfg:
            global_filename = _get_or_wrap_global_cfg(stack, config.global_cfg)
            pytest_args += ["--tavern-global-cfg", global_filename]
        return pytest.main(args=pytest_args)


def run_legacy(  # type:ignore
    in_file: str,
    tavern_global_cfg: Union[dict, str, None] = None,
    tavern_mqtt_backend: Union[str, None] = None,
    tavern_http_backend: Union[str, None] = None,
    tavern_grpc_backend: Union[str, None] = None,
    tavern_strict: Union[bool, None] = None,
    pytest_args: Union[list, None] = None,
) -> Union[ExitCode, int]:
    """Legacy run function for backward compatibility.

    This function is deprecated. Use run() with TavernConfig instead.
    """
    config = TavernConfig(
        in_file=in_file,
        global_cfg=tavern_global_cfg,
        mqtt_backend=tavern_mqtt_backend,
        http_backend=tavern_http_backend,
        grpc_backend=tavern_grpc_backend,
        strict=tavern_strict,
        pytest_args=pytest_args,
    )
    return run(config)
