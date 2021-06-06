from contextlib import ExitStack
from copy import deepcopy
from distutils.util import strtobool
import functools
import logging

from tavern._core import exceptions
from tavern._core.plugins import (
    get_expected,
    get_extra_sessions,
    get_request_type,
    get_verifiers,
)
from tavern._core.strict_util import StrictLevel

from .dict_util import format_keys, get_tavern_box
from .pytest import call_hook
from .report import attach_stage_content, wrap_step
from .testhelpers import delay, retry

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
                        "Unknown stage reference: {}".format(ref_id)
                    )
            else:
                logger.error("Bad stage: 'ref' type must specify 'id'")
                raise exceptions.BadSchemaError("'ref' stage type must specify 'id'")
        test_stages.append(stage)

    return test_stages


def _get_included_stages(tavern_box, test_block_config, test_spec, available_stages):
    """
    Get any stages which were included via config files which will be available
    for use in this test

    Args:
        available_stages (list): List of stages which already exist
        tavern_box (box.Box): Available parameters for fomatting at this point
        test_block_config (dict): Current test config dictionary
        test_spec (dict): Specification for current test

    Returns:
        list: Fully resolved
    """

    def stage_ids(s):
        return [i["id"] for i in s]

    if test_spec.get("includes"):
        # Need to do this separately here so there is no confusion between global and included stages
        for included in test_spec["includes"]:
            for stage in included.get("stages", {}):
                if stage["id"] in stage_ids(available_stages):
                    raise exceptions.DuplicateStageDefinitionError(
                        "Stage id '{}' defined in stage-included test which was already defined in global configuration".format(
                            stage["id"]
                        )
                    )

        included_stages = []

        for included in test_spec["includes"]:
            if "variables" in included:
                formatted_include = format_keys(included["variables"], tavern_box)
                test_block_config.variables.update(formatted_include)

            for stage in included.get("stages", []):
                if stage["id"] in stage_ids(included_stages):
                    raise exceptions.DuplicateStageDefinitionError(
                        "Stage with specified id already defined: {}".format(
                            stage["id"]
                        )
                    )
                included_stages.append(stage)
    else:
        included_stages = []

    return included_stages


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
        global_cfg (TestConfig): Any global configuration for this test

    No Longer Raises:
        TavernException: If any of the tests failed
    """

    # pylint: disable=too-many-locals

    # Initialise test config for this test with the global configuration before
    # starting
    test_block_config = global_cfg.copy()
    default_global_stricness = global_cfg.strict

    tavern_box = get_tavern_box()

    if not test_spec:
        logger.warning("Empty test block in %s", in_file)
        return

    # Get included stages and resolve any into the test spec dictionary
    available_stages = test_block_config.stages
    included_stages = _get_included_stages(
        tavern_box, test_block_config, test_spec, available_stages
    )
    all_stages = {s["id"]: s for s in available_stages + included_stages}
    test_spec["stages"] = _resolve_test_stages(test_spec, all_stages)

    test_block_config.variables["tavern"] = tavern_box["tavern"]

    test_block_name = test_spec["test_name"]

    logger.info("Running test : %s", test_block_name)

    with ExitStack() as stack:
        sessions = get_extra_sessions(test_spec, test_block_config)

        for name, session in sessions.items():
            logger.debug("Entering context for %s", name)
            stack.enter_context(session)

        def getonly(stage):
            o = stage.get("only")
            if o is None:
                return False
            elif isinstance(o, bool):
                return o
            else:
                return strtobool(o)

        has_only = any(getonly(stage) for stage in test_spec["stages"])

        # Run tests in a path in order
        for idx, stage in enumerate(test_spec["stages"]):
            if stage.get("skip"):
                continue
            if has_only and not getonly(stage):
                continue

            test_block_config = test_block_config.with_strictness(
                default_global_stricness
            )
            test_block_config = test_block_config.with_strictness(
                _calculate_stage_strictness(stage, test_block_config, test_spec)
            )

            # Wrap run_stage with retry helper
            run_stage_with_retries = retry(stage, test_block_config)(run_stage)

            partial = functools.partial(
                run_stage_with_retries, sessions, stage, test_block_config
            )

            allure_name = "Stage {}: {}".format(idx, stage["name"])
            step = wrap_step(allure_name, partial)

            try:
                step()
            except exceptions.TavernException as e:
                e.stage = stage
                e.test_block_config = test_block_config
                raise

            if getonly(stage):
                break


def _calculate_stage_strictness(stage, test_block_config, test_spec):
    """Figure out the strictness for this stage

    Can be overridden per stage, or per test

    Priority is global (see pytest _core.util file) <= test <= stage
    """
    stage_options = None
    new_strict = test_block_config.strict

    if test_spec.get("strict", None) is not None:
        stage_options = test_spec["strict"]
        logger.debug("Getting test level strict setting: %s", stage_options)

    stage_strictness_set = None

    def update_stage_options(new_option):
        if stage_strictness_set:
            raise exceptions.DuplicateStrictError
        logger.debug("Setting stage level strict setting: %s", new_option)
        return new_option

    if stage.get("response", {}).get("strict", None) is not None:
        stage_strictness_set = stage_options = update_stage_options(
            stage["response"]["strict"]
        )

    mqtt_response = stage.get("mqtt_response", None)
    if mqtt_response is not None:
        if isinstance(mqtt_response, dict):
            if mqtt_response.get("strict", None) is not None:
                stage_strictness_set = stage_options = update_stage_options(
                    stage["mqtt_response"]["strict"]
                )
        elif isinstance(mqtt_response, list):
            for response in mqtt_response:
                if response.get("strict", None) is not None:
                    stage_strictness_set = stage_options = update_stage_options(
                        response["strict"]
                    )
        else:
            raise exceptions.BadSchemaError(
                "mqtt_response was invalid type {}".format(type(mqtt_response))
            )

    if stage_options is not None:
        if stage_options is True:
            new_strict = StrictLevel.all_on()
        elif stage_options is False:
            new_strict = StrictLevel.all_off()
        else:
            new_strict = StrictLevel.from_options(stage_options)
    else:
        logger.debug("Global default strictness used for this stage")

    logger.debug("Strict key checking for this stage is '%s'", test_block_config.strict)

    return new_strict


def run_stage(sessions, stage, test_block_config):
    """Run one stage from the test

    Args:
        sessions (dict): Dictionary of relevant 'session' objects used for this test
        stage (dict): specification of stage to be run
        test_block_config (dict): available variables for test
    """
    name = stage["name"]

    attach_stage_content(stage)

    r = get_request_type(stage, test_block_config, sessions)

    tavern_box = test_block_config.variables["tavern"]
    tavern_box.update(request_vars=r.request_vars)

    expected = get_expected(stage, test_block_config, sessions)

    delay(stage, "before", test_block_config.variables)

    logger.info("Running stage : %s", name)

    call_hook(
        test_block_config,
        "pytest_tavern_beta_before_every_request",
        request_args=r.request_vars,
    )

    verifiers = get_verifiers(stage, test_block_config, sessions, expected)

    response = r.run()

    for response_type, response_verifiers in verifiers.items():
        logger.debug("Running verifiers for %s", response_type)
        for v in response_verifiers:
            saved = v.verify(response)
            test_block_config.variables.update(saved)

    tavern_box.pop("request_vars")
    delay(stage, "after", test_block_config.variables)
