"""Runner for executing stages in starlark pipelines."""

import dataclasses
import logging
from typing import Any

from tavern._core.pytest.config import TestConfig

logger: logging.Logger = logging.getLogger(__name__)


@dataclasses.dataclass
class StageResponse:
    """Response from running a stage.

    Attributes:
        success: True if all verifications passed
        failure: True if any verification failed
        response: The response body/headers/cookies/status_code
        request_vars: Any variables captured during the request
        stage_name: Name of the stage that was run
    """

    success: bool
    failure: bool
    response: dict[str, Any]
    request_vars: dict[str, Any]
    stage_name: str


def run_stage(
    stage: dict[str, Any],
    test_config: TestConfig,
    sessions: dict[str, Any] | None = None,
) -> StageResponse:
    """Run a single stage and return the response.

    Args:
        stage: The stage specification dictionary
        test_config: The test configuration with available variables
        sessions: Optional dictionary of session contexts to use for the stage.
                  If None, creates an empty sessions dict.

    Returns:
        StageResponse with the result of running the stage
    """
    stage = dict(stage)  # Make a copy to avoid mutating the original
    stage_name = stage.get("name", "unnamed-stage")

    # Import here to avoid circular imports
    from tavern._core.run import _TestRunner
    from tavern._core.strict_util import StrictLevel
    from tavern._core.tincture import get_stage_tinctures

    # Get default strictness (use all_on as default)
    default_strictness = StrictLevel.all_on()

    # Create a minimal test spec
    test_spec = {"test_name": "starlark-pipeline", "stages": [stage]}

    # Use provided sessions or create empty dict
    if sessions is None:
        sessions = {}

    # Create runner
    runner = _TestRunner(
        default_global_strictness=default_strictness,
        sessions=sessions,
        test_block_config=test_config,
        test_spec=test_spec,
    )

    try:
        # Get tinctures for this stage
        tinctures = get_stage_tinctures(stage, test_spec)

        # Create stage config with strictness
        stage_config = test_config.with_strictness(default_strictness)

        # Run the stage using the internal wrapped method
        runner.wrapped_run_stage(stage, stage_config, tinctures)

        # If we get here, the stage succeeded
        # IMPORTANT: test_config has been mutated - capture the updated variables
        response_dict = _extract_response_data(stage)

        return StageResponse(
            success=True,
            failure=False,
            response=response_dict,
            request_vars=test_config.variables,
            stage_name=stage_name,
        )

    except Exception as e:
        logger.warning("Stage '%s' failed: %s", stage_name, str(e))
        # Even on failure, test_config may have partial updates
        return StageResponse(
            success=False,
            failure=True,
            response={"error": str(e)},
            request_vars=test_config.variables,
            stage_name=stage_name,
        )


def _extract_response_data(stage: dict[str, Any]) -> dict[str, Any]:
    """Extract relevant response data from a stage for starlark.

    This is a helper to create a JSON-serializable dictionary from
    the stage specification that can be inspected in starlark.
    """
    response_block = stage.get("response", {})

    # Return the response spec that was defined
    # The actual response will come from the HTTP call
    return {
        "expected_status": response_block.get("status_code"),
        "has_json_expectation": "json" in response_block,
        "has_header_expectations": "headers" in response_block,
        "has_cookie_expectations": "cookies" in response_block,
    }
