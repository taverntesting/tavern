# Starlark Pipeline Knowledge Base

**Generated:** 2025-04-02
**Language:** Starlark/Darwin
**Type:** Scriptable Test Pipelines

## Overview

Starlark pipelines enable advanced test orchestration in Tavern by allowing test authors to write custom Python-like scripts using the Starlark language. This feature enables multi-stage workflows, dynamic test logic, and complex test scenarios beyond simple single-stage YAML definitions.

## Structure

```
tavern/_core/starlark/
├── __init__.py         # Public API exports
├── starlark_env.py     # Pipeline execution context and built-in functions
└── types.py            # Type conversions between Python and Starlark
```

## Key Classes

| Class | Location | Purpose |
|-------|----------|---------|
| `PipelineContext` | `starlark_env.py` | Dictionary object passed between stages, containing test config and sessions |
| `StarlarkPipelineRunner` | `starlark_env.py` | Orchestrates loading and executing starlark scripts |
| `StageResponse` | `starlark_env.py` | Response structure returned from `run_stage()` |

## New Starlark Built-in Functions

### `load("@tavern_helpers.star", "run_stage")`
Load the built-in `run_stage` function from Tavern's starlark helpers.

**Usage:**
```starlark
load("@tavern_helpers.star", "run_stage")
```

### `run_stage(stage_id: str) -> StageResponse`
Execute a single Tavern test stage by its ID and return the response.

**Parameters:**
- `stage_id`: String identifier of the stage to run (must have an `id` key in the YAML)

**Returns:**
- `StageResponse` object with properties:
  - `failed`: Boolean indicating if the stage failed
  - `status_code`: HTTP status code from the response
  - `response`: Response data dictionary
  - `body`: Response body
  - `json`: Parsed JSON response (if applicable)
  - `headers`: Response headers

**Usage:**
```starlark
load("@tavern_helpers.star", "run_stage")

# Run stages by ID (stage must have an 'id' key in YAML)
resp = run_stage("get_cookie")
if resp.failed:
    fail("Get cookie stage failed")

resp = run_stage("echo_value")
if resp.failed:
    fail("Echo stage failed")

# Access response data
if resp.status_code != 200:
    fail(f"Expected 200 but got {resp.status_code}")
```

### `log(message: str) -> None`
Log a message to stdout at INFO level.

**Parameters:**
- `message`: String to log

**Usage:**
```starlark
log("Starting pipeline execution")
log(stages_by_id)
```

## PipelineContext

The `PipelineContext` is a dictionary object passed through test execution, containing:

```python
{
    "test_config": TestConfig,  # Full test configuration with variables
    "sessions": dict[str, Any]  # Dictionary of session contexts (gzip, mqtt, etc.)
}
```

**Key features:**
- Variables defined in global config are available during execution
- Test config is mutated in-place by `run_stage()` (variables are updated)
- Sessions persist across multiple stages (e.g., MQTT subscriptions)

## Running Tests

Enable the experimental Starlark pipeline feature with the `--tavern-experimental-starlark-pipeline` flag.

```bash
# Run starlark tests
pytest --tavern-experimental-starlark-pipeline tests/integration/starlark/ -v

# Or using tox
tox -q -c tox-integration.ini -e py312 -- --tavern-experimental-starlark-pipeline tests/integration/starlark/

# Requires test server running (see tests/integration/starlark/README.md)
docker-compose up -d server
```

## File Convention

Starlark pipeline files must:
1. End with `.tavern.star` extension (instead of `.tavern.yaml`)
2. Contain at least one `run_pipeline()` function

## Pattern: Inline Control Flow

Tests now use inline Starlark scripts with the `control_flow` key directly in the YAML. Stages are referenced by their `id` rather than passing full stage dictionaries.

### YAML Structure

```yaml
test_name: My test with control flow

stages:
  - name: Get cookie
    id: get_cookie
    request:
      url: "{host}/get_cookie"
      method: POST
    response:
      status_code: 200

# Inline Starlark script
control_flow: |
  load("@tavern_helpers.star", "run_stage")

  # Run stage by ID
  resp = run_stage("get_cookie")
  if resp.failed:
    fail("Stage failed")
```

### With Included Stages

```yaml
test_name: Test with included stages

includes:
  - !include stages.yaml

# Inline Starlark script
control_flow: |
  load("@tavern_helpers.star", "run_stage")

  # Run included stage by ID
  resp = run_stage("get-cookie-included")
  if resp.failed:
    fail("Stage failed")
```

### Pattern Summary

1. Define stages in `stages` key OR include via `includes`
2. Each stage must have an `id` key for Starlark to reference it
3. Add `control_flow` key with inline Starlark script
4. Load `"@tavern_helpers.star"` to get `run_stage` function
5. Call `run_stage("stage_id")` with the stage's string ID
6. Check `resp.failed` or `resp.status_code` for verification

## Type Conversions

`types.py` provides bidirectional conversion between Python and Starlark:

- **Starlark → Python**: `from_starlark(obj)` - Unwraps `OpaquePythonObject` and reconstructs Python objects
- **Python → Starlark**: `to_starlark(obj)` - Wraps Python objects in `OpaquePythonObject` to pass through Starlark's JSON-only environment

Types handled:
- Primitives: `str`, `int`, `float`, `bool`, `None`
- Collections: `dict`, `list`, `tuple`
- Custom objects: Calls `to_starlark()` method (if implemented)

## Notes

- Starlark is a restricted Python-like language for build systems
- Enables test orchestration beyond single-stage YAML definitions
- Integration tests require the test server to be running
- Code in `tavern/_core/starlark/` is part of the core library
