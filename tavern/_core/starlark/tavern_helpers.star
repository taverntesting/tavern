"""Tavern helper functions for Starlark scripts.

This module provides built-in functions for controlling test execution
in Tavern's Starlark pipeline feature.

Usage:
    load("@tavern_helpers.star", "run_stage", "re", "time", "log")
"""


def run_stage(name, *, continue_on_fail=False, extra_vars=None):
    """Execute a test stage by its ID and return the response.

    Args:
        name: Stage ID to execute (must have 'id' key in YAML)
        continue_on_fail: If True, return failed response instead of raising
            an exception. Default: False
        extra_vars: Optional dict of variables to merge into stage config

    Returns:
        A struct with properties:
            - failed (bool): True if stage failed
            - success (bool): True if stage succeeded
            - request_vars: Variables captured during request execution
            - stage_name: Name of the executed stage

        For HTTP responses, also includes:
            - body: Response body (parsed JSON if Content-Type is application/json)
            - status_code: HTTP status code
            - headers: Response headers
            - cookies: Response cookies

    Example:
        # Run a stage by ID
        resp = run_stage("get_cookie")
        if resp.failed:
            fail("Stage failed")

        # Continue on failure
        resp = run_stage("try_login", continue_on_fail=True)
        if resp.failed:
            log("Login failed, using fallback")
            run_stage("fallback_login")
    """
    resp = __run_stage(name, continue_on_fail, extra_vars)
    return struct(**resp)


def _re_match(pattern, s):
    """Match a regex pattern at the beginning of string.

    Args:
        pattern: Regular expression pattern
        s: String to match against

    Returns:
        A struct with match details, or None if no match:
            - group0: Full match (group 0)
            - groups: List of captured groups
            - start: Start position of match
            - end: End position of match
    """
    m = __re_match(pattern, s)
    if m == None:
        return None
    return struct(group0=m["group0"], groups=m["groups"], start=m["start"], end=m["end"])


def _re_search(pattern, s):
    """Search for a regex pattern anywhere in string.

    Args:
        pattern: Regular expression pattern
        s: String to search in

    Returns:
        A struct with match details, or None if no match:
            - group0: Full match (group 0)
            - groups: List of captured groups
            - start: Start position of match
            - end: End position of match
    """
    m = __re_search(pattern, s)
    if m == None:
        return None
    return struct(group0=m["group0"], groups=m["groups"], start=m["start"], end=m["end"])


def _re_sub(pattern, repl, s):
    """Substitute occurrences of pattern in string.

    Args:
        pattern: Regular expression pattern
        repl: Replacement string
        s: String to process

    Returns:
        String with all occurrences replaced
    """
    return __re_sub(pattern, repl, s)


re = struct(match=_re_match, search=_re_search, sub=_re_sub)
"""Regex utilities for pattern matching and text manipulation.

Provides Python regex-style operations for use in Starlark scripts.

Available methods:
    match(pattern, string): Match pattern at start of string
    search(pattern, string): Search for pattern anywhere in string
    sub(pattern, repl, string): Replace all pattern occurrences

Example:
    load("@tavern_helpers.star", "re")

    resp = run_stage("get_data")

    # Extract version number
    match = re.search("v(\\d+)\\.", resp.body)
    if match == None:
        fail("Version not found")
    version = match.groups[0]

    # Replace values
    new_url = re.sub("OLD", "NEW", original_url)
"""


def _time_sleep(seconds):
    """Sleep for specified seconds.

    Args:
        seconds: Number of seconds to sleep (can be float)

    Example:
        time.sleep(0.5)  # Sleep for 500ms
    """
    __time_sleep(seconds)


time = struct(sleep=_time_sleep)
"""Time utilities for delays and timing operations.

Available methods:
    sleep(seconds): Pause execution for given seconds

Example:
    load("@tavern_helpers.star", "time")

    for i in range(0, 3):
        resp = run_stage("poll", continue_on_fail=True)
        if not resp.failed:
            break
        time.sleep(1)  # Wait 1 second before retry
"""