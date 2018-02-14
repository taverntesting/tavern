import logging

import yaml

from contextlib2 import ExitStack

from .util import exceptions
from .util.loader import IncludeLoader
from .util.env_vars import check_env_var_settings
from .request import RestRequest, MQTTRequest
from .response import RestResponse, MQTTResponse
from .printer import log_pass, log_fail

from .schemas.files import verify_tests


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
    # Initialise test config for this test with the global configuration before
    # starting

    test_block_config = dict(global_cfg)

    if "variables" not in test_block_config:
        test_block_config["variables"] = {}

    if not test_spec:
        logger.warning("Empty test block in %s", in_file)
        return

    if test_spec.get("includes"):
        for included in test_spec["includes"]:
            if "variables" in included:
                check_env_var_settings(included["variables"])
                test_block_config["variables"].update(included["variables"])

    test_block_name = test_spec["test_name"]

    logger.info("Running test : %s", test_block_name)

    with ExitStack() as stack:
        if "mqtt" in test_spec:
            from .mqtt import MQTTClient
            try:
                _client = MQTTClient(**test_spec["mqtt"])
                mqtt_client = stack.enter_context(_client)
            except exceptions.MQTTError:
                log_fail({"name": "initializing mqtt"}, None, None)
                raise
        else:
            mqtt_client = None

        # Run tests in a path in order
        for stage in test_spec["stages"]:
            name = stage["name"]

            mqtt_expected = None
            expected = None

            # FIXME
            # This can be simplified somehow

            if "request" in stage:
                expected = stage["response"]
                rspec = stage["request"]

                try:
                    r = RestRequest(rspec, test_block_config)
                except exceptions.MissingFormatError:
                    log_fail(stage, None, expected)
                    raise
            elif "mqtt_publish" in stage:
                if not mqtt_client:
                    logger.error("No mqtt settings but stage wanted to send an mqtt message")
                    log_fail(stage, None, expected)
                    raise exceptions.MissingSettingsError

                # mqtt response is not required
                mqtt_expected = stage.get("mqtt_response")
                rspec = stage["mqtt_publish"]

                try:
                    r = MQTTRequest(mqtt_client, rspec, test_block_config)
                except exceptions.MissingFormatError:
                    log_fail(stage, None, expected)
                    raise
            else:
                logger.error("Need to specify either 'request' or 'mqtt_publish'")
                log_fail(stage, None, expected)
                raise exceptions.MissingKeysError

            logger.info("Running stage : %s", name)

            response = r.run()

            verifiers = []
            if expected:
                verifiers.append(RestResponse(name, expected, test_block_config))
            if mqtt_expected:
                verifiers.append(MQTTResponse(mqtt_client, name, mqtt_expected, test_block_config))

            for v in verifiers:
                try:
                    saved = v.verify(response)
                except exceptions.TavernException:
                    log_fail(stage, v, expected)
                    raise
                else:
                    test_block_config["variables"].update(saved)

            log_pass(stage, verifiers)


def run(in_file, tavern_global_cfg):
    """Run all tests contained in a file

    For each test this makes sure it matches the expected schema, then runs it.
    There currently isn't something like pytest's `-x` flag which exits on first
    failure.

    Args:
        in_file (str): file to run tests on
        tavern_global_cfg (str): file containing Global config for all tests

    Returns:
        bool: Whether ALL tests passed or not
    """

    passed = True

    if tavern_global_cfg:
        with open(tavern_global_cfg, "r") as gfileobj:
            global_cfg = yaml.load(gfileobj)
    else:
        global_cfg = {}

    with open(in_file, "r") as infile:
        # Multiple documents per file => multiple test paths per file
        for test_spec in yaml.load_all(infile, Loader=IncludeLoader):
            if not test_spec:
                logger.warning("Empty document in input file '%s'", in_file)
                continue

            try:
                verify_tests(test_spec)
            except exceptions.BadSchemaError:
                passed = False
                continue

            try:
                run_test(in_file, test_spec, global_cfg)
            except exceptions.TestFailError:
                passed = False
                continue

    return passed
