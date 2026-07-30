"""Conversion of a plugin response object into a dict for use in Starlark.

This is used both by the full ``control_flow`` pipeline (where it becomes the struct
returned by ``run_stage()``) and by per-stage ``retry_until`` expressions.
"""

from typing import Any

import requests


def create_response_struct(
    response: Any | None,
    *,
    success: bool,
    request_vars: dict[str, Any],
    stage_name: str,
) -> dict[str, Any]:
    """Convert a response from running a stage into a dict of Starlark-safe values.

    The returned dict is intended to be splatted into a Starlark ``struct()`` so that
    users can write ``response.status_code`` etc.

    Args:
        response: the response from the plugin that ran the stage, if any
        success: whether the stage passed all of its verifications
        request_vars: any variables captured during the request
        stage_name: name of the stage that was run

    Returns:
        dict of response values

    Raises:
        NotImplementedError: if the response is from a plugin which is not supported yet
    """
    base_dict: dict[str, Any] = {
        # Add "failed" so people don't have to do "if not resp.success" when people will almost certainly
        # want to do "if resp.failed" most of the time
        "failed": not success,
        "success": success,
        "request_vars": request_vars,
        "stage_name": stage_name,
    }

    if response is None:
        return base_dict

    if isinstance(response, requests.Response):
        content_type = response.headers.get("Content-Type", "")

        # Try to parse JSON body, fall back to raw content
        if "application/json" in content_type:
            body = response.json()
        else:
            body = response.content

        base_dict.update(
            {
                "status_code": response.status_code,
                "body": body,
                "headers": response.headers,
                "cookies": response.cookies,
            }
        )
        return base_dict

    raise NotImplementedError(
        f"gRPC, MQTT, etc. are not supported yet. Got {type(response)}"
    )
