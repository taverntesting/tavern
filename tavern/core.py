import logging
import warnings
import os
from copy import deepcopy

import pytest

from contextlib2 import ExitStack
from box import Box

from .util import exceptions
from .util.dict_util import format_keys
from .util.delay import delay
from .util.retry import retry

from .plugins import get_extra_sessions, get_request_type, get_verifiers, get_expected
from .schemas.files import wrapfile


logger = logging.getLogger(__name__)

def _resolve_test_stages(test_spec, available_stages):
    # Need to get a final list of stages in the tests (resolving refs)
    test_stages = []
    for raw_stage in test_spec["stages"]:
        stage = raw_stage
        if stage.get("type") == "ref":
            if "id" in stage:
                ref_id = stage["id"]
                if ref_id in available_stages:
                    # Make sure nothing downstream can change the globally
                    # defined stage. Just give the test a local copy.
                    stage = deepcopy(available_stages[ref_id])
                    logger.debug("found stage reference: %s", ref_id)
                else:
                    logger.error("Bad stage: unknown stage referenced: %s", ref_id)
                    raise exceptions.InvalidStageReferenceError(
                        "Unknown stage reference: {}".format(ref_id))
            else:
                logger.error("Bad stage: 'ref' type must specify 'id'")
                raise exceptions.BadSchemaError(
                    "'ref' stage type must specify 'id'")
        test_stages.append(stage)

    return test_stages

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

    No Longer Raises:
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

    if not test_spec:
        logger.warning("Empty test block in %s", in_file)
        return

    available_stages = {}
    if test_spec.get("includes"):
        for included in test_spec["includes"]:
            if "variables" in included:
                formatted_include = format_keys(included["variables"], {"tavern": tavern_box})
                test_block_config["variables"].update(formatted_include)

            if "stages" in included:
                for stage in included["stages"]:
                    if stage["id"] in available_stages:
                        raise exceptions.DuplicateStageDefinitionError(
                            "Stage with specified id already defined: {}".format(stage["id"]))
                    available_stages[stage["id"]] = stage

    test_block_config["variables"]["tavern"] = tavern_box

    test_block_name = test_spec["test_name"]

    # Strict on body by default
    default_strictness = test_block_config["strict"]

    logger.info("Running test : %s", test_block_name)

    with ExitStack() as stack:
        test_spec["stages"] = _resolve_test_stages(test_spec, available_stages)
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

            run_stage_ = run_stage
            if stage.get('max_retries'):
                run_stage_ = retry(stage)(run_stage_)

            try:
                run_stage_(sessions, stage, tavern_box, test_block_config)
            except exceptions.TavernException as e:
                e.stage = stage
                e.test_block_config = test_block_config
                raise

            if stage.get('only'):
                break


def run_stage(sessions, stage, tavern_box, test_block_config):
    """Run one stage from the test

    Args:
        sessions (list): List of relevant 'session' objects used for this test
        stage (dict): specification of stage to be run
        tavern_box (box.Box): Box object containing format variables to be used
            in test
        test_block_config (dict): available variables for test
    """
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
        tavern_mqtt_backend (str, optional): name of MQTT plugin to use. If not
            specified, uses tavern-mqtt
        tavern_http_backend (str, optional): name of HTTP plugin to use. If not
            specified, use tavern-http
        tavern_strict (bool, optional): Strictness of checking for responses.
            See documentation for details
        pytest_args (list, optional): List of extra arguments to pass directly
            to Pytest as if they were command line arguments
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
        **kwargs: any extra arguments to pass to _run_pytest, see that function
            for details

    Returns:
        bool: False if there were test failures, True otherwise
    """
    return _run_pytest(in_file, tavern_global_cfg, **kwargs)
