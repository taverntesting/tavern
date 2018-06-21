import logging
import warnings
import os

import pytest

from contextlib2 import ExitStack
from box import Box

from .util import exceptions
from .util.dict_util import format_keys
from .util.delay import delay

from .plugins import get_extra_sessions, get_request_type, get_verifiers, get_expected
from .schemas.files import wrapfile


logger = logging.getLogger(__name__)


def run_test(in_file, test_spec, global_cfg):
    """Run a single tavern test

    Note that each tavern test can consist of multiple requests (log in,
    create, update, delete, etc).

    The global configuration is copied and used as an initial configuration for
    this test. Any values which are saved from any tests are saved into this
    test block and can be used for formatting in later stages in the test.

    Args:
        in_file (str): filename containing this test
        test_spec (dict): The specification for this test
        global_cfg (dict): Any global configuration for this test

    Raises:
        TavernException: If any of the tests failed
    """

    # pylint: disable=too-many-locals

    # Initialise test config for this test with the global configuration before
    # starting
    test_block_config = dict(global_cfg)

    if "variables" not in test_block_config:
        test_block_config["variables"] = {}

    tavern_box = Box({
        "env_vars": dict(os.environ),
    })

    test_block_config["variables"]["tavern"] = tavern_box

    if not test_spec:
        logger.warning("Empty test block in %s", in_file)
        return

    if test_spec.get("includes"):
        for included in test_spec["includes"]:
            if "variables" in included:
                formatted_include = format_keys(included["variables"], {"tavern": tavern_box})
                test_block_config["variables"].update(formatted_include)

    test_block_name = test_spec["test_name"]

    # Strict on body by default
    default_strictness = test_block_config["strict"]

    logger.info("Running test : %s", test_block_name)

    with ExitStack() as stack:
        sessions = get_extra_sessions(test_spec, test_block_config)

        for name, session in sessions.items():
            logger.debug("Entering context for %s", name)
            stack.enter_context(session)

        # Run tests in a path in order
        for stage in test_spec["stages"]:
            if stage.get('skip'):
                continue

            test_block_config["strict"] = default_strictness

            # Can be overridden per stage
            # NOTE
            # this is hardcoded to check for the 'response' block. In the far
            # future there might not be a response block, but at the moment it
            # is the hardcoded value for any HTTP request.
            if stage.get("response", {}):
                if stage.get("response").get("strict", None) is not None:
                    stage_strictness = stage.get("response").get("strict", None)
                elif test_spec.get("strict", None) is not None:
                    stage_strictness = test_spec.get("strict", None)
                else:
                    stage_strictness = default_strictness

                logger.debug("Strict key checking for this stage is '%s'", stage_strictness)

                test_block_config["strict"] = stage_strictness
            elif default_strictness:
                logger.debug("Default strictness '%s' ignored for this stage", default_strictness)

            try:
                run_stage(sessions, stage, tavern_box, test_block_config)
            except exceptions.TavernException as e:
                e.stage = stage
                e.test_block_config = test_block_config
                raise

            if stage.get('only'):
                break


def run_stage(sessions, stage, tavern_box, test_block_config):
    name = stage["name"]

    r = get_request_type(stage, test_block_config, sessions)

    tavern_box.update(request_vars=r.request_vars)

    expected = get_expected(stage, test_block_config, sessions)

    delay(stage, "before")

    logger.info("Running stage : %s", name)
    response = r.run()

    verifiers = get_verifiers(stage, test_block_config, sessions, expected)
    for v in verifiers:
        saved = v.verify(response)
        test_block_config["variables"].update(saved)

    tavern_box.pop("request_vars")
    delay(stage, "after")


def _run_pytest(in_file, tavern_global_cfg, tavern_mqtt_backend=None, tavern_http_backend=None, tavern_strict=None, pytest_args=None, **kwargs): # pylint: disable=too-many-arguments
    """Run all tests contained in a file using pytest.main()

    Args:
        in_file (str): file to run tests on
        tavern_global_cfg (dict): Extra global config
        ptest_args (list): Extra pytest args to pass

        **kwargs (dict): ignored

    Returns:
        bool: Whether ALL tests passed or not
    """

    if kwargs:
        warnings.warn("Passing extra keyword args to run() when using pytest is used are ignored.", FutureWarning)

    with ExitStack() as stack:

        if tavern_global_cfg:
            global_filename = stack.enter_context(wrapfile(tavern_global_cfg))

        pytest_args = pytest_args or []
        pytest_args += ["-k", in_file]
        if tavern_global_cfg:
            pytest_args += ["--tavern-global-cfg", global_filename]

        if tavern_mqtt_backend:
            pytest_args += ["--tavern-mqtt-backend", tavern_mqtt_backend]
        if tavern_http_backend:
            pytest_args += ["--tavern-http-backend", tavern_http_backend]
        if tavern_strict:
            pytest_args += ["--tavern-strict", tavern_strict]

        return pytest.main(args=pytest_args)


def run(in_file, tavern_global_cfg=None, **kwargs):
    """Run tests in file

    Args:
        in_file (str): file to run tests for
        tavern_global_cfg (dict): Extra global config
    """
    return _run_pytest(in_file, tavern_global_cfg, **kwargs)
