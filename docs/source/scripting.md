# Scripting Tavern execution with Starlark

Tavern supports advanced test orchestration through Starlark scripting, enabling complex control flow, dynamic test
logic, and multi-stage workflows beyond simple sequential YAML tests.

**This should be considered an experimental work in progress feature and some functionality may change without a major
version bump.**

**This should also only be used when other control flow options are not suitable. Using scripting can make tests harder
to debug, but can be useful for more complex test scenarios.**

## What problem is this trying to solve?

In GitHub actions, stage execution is sequential (like Tavern) but stages can be conditionally executed based on
previous stage results using magic string substitutions, eg:

```yaml
name: basic test

on:
  pull_request:
    branches:
      - main

jobs:
  simple-checks:
    runs-on: ubuntu-24.04

    steps:
      - uses: actions/checkout@v6

      - name: Do something
        id: do-something
        uses: do-something-action@v1

      - name: Do something else
        if: ${{ steps.do-something.outputs.success == 'true' }}
        uses: do-something-else-action@v2
```

Tavern emulates some of this behaviour already, with
the ['skip' key](./core_concepts/marks.md#skipping-stages-with-simpleeval-expressions), and has some limited support for
retries with the ['max_retries' key](./core_concepts/flow.md#retrying-tests). There are other control flow features like
[adding a delay](./core_concepts/flow.md#adding-a-delay-between-tests), each of which have their own specific syntax for
use.

To try and combine all of these into one unified test execution model, we need a way to express complex logic
declaratively, in a format that is more readable than interpolated strings in YAML.

There are two levels to this:

- [Per-stage expressions](#per-stage-expressions) (`if`, `retry_until` and `fail_if`) - keep the normal sequential stage list and
  just annotate individual stages. This is the closest thing to the GitHub Actions example above and is where you
  should start.
- A full [`control_flow` script](#basic-usage) - replaces sequential execution entirely, for things which can't be
  expressed as a per-stage condition (loops over entities, fallback paths, extracting values with regexes, etc).

## Starlark Overview

Starlark is a Python-like language designed for configuration and build systems. It provides:

- Python-like syntax familiar to most developers
- Deterministic execution (not turing complete)
- Safe, sandboxed environment
- Built-in control flow: `if/elif/else`, `for`
- Basic types: `str`, `int`, `list`, etc.
- Basic built-in functions: `len()`, `max()`, `min()`, `type()`, `sorted()`

## Enabling Starlark

Starlark control flow is an experimental feature. Enable it with the pytest flag:

```bash
pytest --tavern-experimental-starlark-pipeline
```

## Per-stage expressions

Rewriting a whole test as a `control_flow` script is a lot of ceremony if all you want is "only run this stage if the
last one returned something". For that, stages support two keys which are single Starlark _expressions_, evaluated by
the same embedded interpreter. There is no script, no `load()`, and stages do not need an `id`. These need the same
`--tavern-experimental-starlark-pipeline` flag as `control_flow`.

Test variables - anything from `save`, `includes`, global config, fixtures, parametrisation, and the `tavern` box - are
referred to with the same `{format_string}` syntax as everywhere else in Tavern. The expression is interpolated first
and the result is what gets evaluated, so `if: "{var_x} > 2"` with `var_x` saved as `3` evaluates `3 > 2`. Referring to
a variable which does not exist is an error, and error messages include both the original expression and the
interpolated one.

Two things follow from this which are worth being aware of:

> **Quote your strings.** A string variable is interpolated in as-is, not as a Starlark string literal, so write
> `if: "'{name}' == 'bob'"` rather than `if: "{name} == 'bob'"` - the latter evaluates `bob == 'bob'` and fails with an
> undefined name.
>
> **Escape literal braces.** A Starlark dict or set literal in an expression needs doubled braces, as in
> `if: "{{'a': 1}}['a'] == 1"`.

Because interpolation happens before evaluation, variable names which are not valid Starlark identifiers - anything
with a dash in it, or a Starlark reserved word - work fine.

### Running a stage conditionally with `if`

The stage only runs if the expression evaluates to `True`. This is an alternative to the
['skip' key](./core_concepts/marks.md#skipping-stages-with-simpleeval-expressions) - `if` is the same thing with the
logic inverted, and a stage cannot use both.

```yaml
stages:
  - name: Create a user
    request:
      url: "{global_host}/users"
      method: POST
    response:
      status_code: 201
      save:
        json:
          n_existing: existing_count

  - name: Only tidy up if there was something there already
    if: "{n_existing} > 0"
    request:
      url: "{global_host}/users/cleanup"
      method: POST
    response:
      status_code: 200
```

The expression must evaluate to a boolean, and referring to a variable which has not been saved yet is an error rather
than being treated as false.

`if` is only evaluated for normal stages - stages in a [`finally` block](./core_concepts/flow.md#finalising-stages)
always run.

### Polling with `retry_until`

`retry_until` is a second opinion on a stage that **failed**. It works like `max_retries`, except that instead of
blindly retrying it lets you say when to stop:

- If the stage **passes**, it is finished. **`retry_until` is not evaluated at all** - a passing stage is never retried,
  even if the expression would have been `False`.
- If the stage **fails**, `retry_until` is evaluated against the response that came back. If it is `True` the stage is
  treated as finished and the test carries on to the next stage, even though the response block did not match. If it is
  `False` the stage is retried, up to `max_retries` times, sleeping for `delay_after` in between.
- If the stage never passes and `retry_until` is never `True`, the test fails.

In other words, adding `retry_until` gives the stage something like the `continue_on_fail` behaviour of
[`run_stage()`](#run_stage), with the expression deciding when to give up retrying and call it a success.

```yaml
stages:
  - name: Poll until the job is ready
    request:
      url: "{global_host}/poll"
      method: GET
    response:
      status_code: 200
      json:
        status: ready
    max_retries: 20
    delay_after: 1
    retry_until: response.body["status"] == "ready"
```

As well as the test variables, the expression has a `response` struct in scope with the same properties as the one
returned by [`run_stage()`](#run_stage):

```starlark
response.status_code == 200 and response.body["status"] == "{expected_status}"
```

Because it is an arbitrary expression it can also stop on more than one outcome, which is the usual shape for polling a
long running job that might end up in any one of several terminal states:

```yaml
stages:
  - name: Poll until the job finishes
    request:
      url: "{global_host}/job/{job_id}"
      method: GET
    response:
      status_code: 200
      json:
        status: SUCCESS
    max_retries: 20
    delay_after: 1
    retry_until: response.body["status"] == "SUCCESS" or response.body["status"] == "FAILED"
```

Here the `response` block says what the happy path looks like, and `retry_until` says when there is no point polling any
more. A job which ends up as `FAILED` stops the retries immediately rather than waiting out all 20 of them - but note
that, as above, a stage which finished because `retry_until` was `True` does not fail the test even though its response
block did not match. If you need to assert on how the job actually ended, do it in a following stage.

Note that:

- `max_retries` is required - `retry_until` without it is a schema error.
- Because `retry_until` is only consulted on failure, an expression which is already implied by the `response` block
  will never be evaluated. Write the `response` block for what you expect once the polling has finished, as in the
  example above.
- If the request itself failed and no response was received at all (a connection error, say) there is nothing to
  evaluate the expression against, so the stage is just retried.
- Values in the `save` block of an attempt which failed verification are **not** saved, so if a stage finishes because
  `retry_until` was `True` rather than because it passed, later stages will not see them.
- `retry_until` does not apply inside a `control_flow` script, which bypasses the retry machinery - use
  `run_stage(..., continue_on_fail=True)` in a `for` loop instead, as shown in [Retry and Polling](#retry-and-polling).

### Failing fast with `fail_if`

`fail_if` is the mirror image of `retry_until` - a negative assertion which fails the stage as soon as it is `True`:

- It is evaluated after **every** attempt at the stage, whether that attempt passed or failed.
- If it is `True` the test fails immediately. The stage is **not** retried, no matter what `max_retries` or
  `retry_until` say.
- If it is `False` nothing changes - a stage which passed carries on to the next stage, and a stage which failed is
  retried as normal.

It has the same `response` struct in scope as `retry_until`, which includes `response.failed` if you want to
distinguish an attempt which passed its response block from one which did not.

The main use for this is polling something which can end up in a state it will never recover from. `retry_until` alone
can only say "stop polling", which counts as a pass; `fail_if` says "stop polling, and this is a failure":

```yaml
stages:
  - name: Poll until the job succeeds
    request:
      url: "{global_host}/job/{job_id}"
      method: GET
    response:
      status_code: 200
      json:
        status: SUCCESS
    max_retries: 60
    delay_after: 10
    retry_until: response.body["status"] == "SUCCESS"
    fail_if: response.body["status"] == "FAILED"
```

A job which goes to `FAILED` fails the test on the next poll instead of spending ten minutes retrying something which
was never going to succeed.

It is also useful on its own, with no retries at all, as an assertion which is easier to express as an expression than
as a `response` block:

```yaml
- name: Check the response does not leak internal errors
  request:
    url: "{global_host}/search"
    method: GET
  response:
    status_code: 200
  fail_if: 'response.body["message"] != None and "traceback" in response.body["message"]'
```

Note that:

- Unlike `retry_until`, `fail_if` does not need `max_retries`.
- If the request itself failed and no response was received at all, `fail_if` is not evaluated and the stage fails or
  retries as it normally would.
- Like `retry_until`, it does not apply inside a `control_flow` script - check the struct returned by `run_stage()`
  instead.

## Basic Usage

### Inline Control Flow

Define Starlark scripts directly in your YAML using the `control_flow` key:

```yaml
---
test_name: Test control_flow with inline Starlark - basic sequential

stages:
  - name: Get cookie
    id: get_cookie
    request:
      url: "{global_host}/get_cookie"
      method: POST
      json:
        cookie_name: test-cookie
    response:
      status_code: 200
      cookies:
        - test-cookie

  - name: Echo a value
    id: echo_value
    request:
      url: "{global_host}/echo"
      method: POST
      json:
        value: "hello"
    response:
      status_code: 200
      json:
        value: "hello"

# Inline Starlark script that controls execution order
control_flow: |
  # Load the stage runner helper
  load("@tavern_helpers.star", "run_stage")

  # First run the get_cookie stage. If this fails, it will fail the test.
  resp = run_stage("get_cookie")

  # Then run the echo_value stage
  resp = run_stage("echo_value")
```

This key being present will _override_ the default sequential test execution.

Notes about the execution model:

- All existing Tavern functionality remains the same. Pytest fixtures and marks are applied (including `parametrize`),
  tinctures are run between stages, Tavern hooks are called.
- [`finally` stages](./core_concepts/flow.md#finalising-stages) are _not_ run.
- If `run_stage()` is not called, an exception will be raised. This mirrors Pytest's default behaviour, where it will
  exit with exit code 1 if no tests were run.

### Stage Requirements

Each stage referenced from Starlark must have an `id` key:

```yaml
stages:
  - name: My stage name
    id: my_stage_id    # Required for Starlark reference
    request:
    # ... request config
```

## Available Functions

See [the autogenerated scripting API docs](./scripting-api.md) for a complete list of available functions.

### `run_stage()`

Execute a test stage by its ID:

```starlark
load("@tavern_helpers.star", "run_stage")

# Basic usage
resp = run_stage("stage_id")

# Continue even if stage fails, fall back to login if necessary
resp = run_stage("try_get_user_data", continue_on_fail=True)
if resp.failed:
    log("Login failed")
    run_stage("login")
    run_stage("try_get_user_data")

# Pass variables to the stage
resp = run_stage("verify_data", extra_vars={
    "key": "value",
    "user_id": extracted_id
})
```

**Parameters:**

- `name` (string, required): Stage ID to execute
- `continue_on_fail` (bool, optional): If `True`, return a failed response instead of raising an exception. Default:
  `False`
- `extra_vars` (dict, optional): Additional variables to merge into the stage's configuration

**Return value:** A response struct with properties:

- `.failed` (bool): `True` if the stage failed
- `.success` (bool): `True` if the stage succeeded
- `.request_vars`: Variables captured during request execution
- `.stage_name`: Name of the executed stage

The struct also has properties specific to the response type, currently only available for HTTP responses:

- `.body`: Response body (parsed JSON if `Content-Type` is `application/json`, otherwise raw bytes)
- `.status_code`: HTTP status code
- `.headers`: Response headers
- `.cookies`: Response cookies

### Regex Functions

Pattern matching and extraction via the `re` module:

```starlark
load("@tavern_helpers.star", "run_stage", "re")

# Get data containing text to match
resp = run_stage("get_data")

# re.search returns a struct with: group0, groups, start, end
version_match = re.search("v(\\d+)\\.", resp.body)
if version_match == None:
    fail("Failed to match version pattern")

# Access captured groups
major_version = version_match.groups[0]

# Use extracted values in next stage
resp = run_stage("verify", extra_vars={
    "major_version": major_version
})
```

**Available regex functions:**

- `re.match(pattern, string)`: Match at the beginning of the string
- `re.search(pattern, string)`: Search anywhere in the string
- `re.sub(pattern, replacement, string)`: Substitute pattern matches

**Return value for match/search:** A struct with:

- `.group0`: The full match (group 0)
- `.groups`: List of captured groups
- `.start`: Start position of the match
- `.end`: End position of the match

Returns `None` if no match found.

### `log()`

Log messages to stdout at INFO level:

```starlark
log("Starting pipeline execution")
log("Stage completed with status: " + resp.status_code)
```

### `fail()`

Explicitly fail the test with a message:

```starlark
if resp.failed:
    fail("Stage failed unexpectedly")
```

## Working with Included Stages

Stages defined in included files can be referenced by their IDs:

```yaml
---
test_name: Test control_flow with included stages

includes:
  - !include stages.yaml

# Inline Starlark script using included stage IDs
control_flow: |
  load("@tavern_helpers.star", "run_stage")

  # Run stages defined in stages.yaml
  resp = run_stage("get-cookie-included")
  resp = run_stage("echo-value-included")

  if resp.failed:
    fail("Included stage failed")
```

Stages defined in global configuration are also available:

```yaml
# Run with --tavern-global-cfg /path/to/global_cfg.yaml
---
test_name: Test with global stages

control_flow: |
  load("@tavern_helpers.star", "run_stage")

  # Run a stage defined in global_cfg.yaml
  run_stage("finally-nothing-check")
```

## Programming Patterns

### Extracting and Using Response Data

Use regex to extract values from responses and pass them to subsequent stages:

```yaml
---
test_name: Test regex extraction with inline Starlark

stages:
  - name: Get regex test data
    id: get_regex_data
    request:
      url: "{global_host}/regex_data"
      method: GET
    response:
      status_code: 200

  - name: Verify extracted values
    id: verify_extracted
    request:
      url: "{global_host}/verify_extracted"
      method: POST
      json:
        major_version: "{major_version}"
        token_id: "{token_id}"
        server_name: "{server_name}"
    response:
      status_code: 200
      json:
        status: "verified"

control_flow: |
  load("@tavern_helpers.star", "run_stage", "re")

  # Get data
  resp = run_stage("get_regex_data")
  if resp.failed:
    fail("get_regex_data stage failed")

  # Extract version: v2.5.1 -> capture major version "2"
  version_match = re.search("v(\\d+)\\.", resp.body)
  if version_match == None:
    fail("Failed to match version pattern")
  major_version = version_match.groups[0]

  # Extract token: TKN-a1b2c3d4e5f6 -> capture ID part
  token_match = re.search("\"TKN-(.+)\"", resp.body)
  if token_match == None:
    fail("Failed to match token pattern from " + resp.body)
  token_id = token_match.groups[0]

  # Extract server: Server-PROD-01 -> capture "PROD-01"
  server_match = re.search("Server-(\\w+-\\w+)\\s", resp.body)
  if server_match == None:
    fail("Failed to match server pattern")
  server_name = server_match.groups[0]

  # Pass extracted values via extra_vars
  resp = run_stage("verify_extracted", extra_vars={
    "major_version": major_version,
    "token_id": token_id,
    "server_name": server_name
  })
  if resp.failed:
    fail("verify_extracted stage failed")
```

### Retry and Polling

Implement retry logic with `continue_on_fail`:

```yaml
test_name: test for loop with retry

stages:
  - name: polling
    id: polling
    request:
      url: "{global_host}/poll"
      method: GET
    response:
      status_code: 200
      json:
        status: ready

control_flow: |
  load("@tavern_helpers.star", "run_stage", "time")

  succeeded = False
  for i in range(0, 3):
      resp = run_stage("polling", continue_on_fail=True)
      if not resp.failed:
          succeeded = True
          break
      log("polling attempt " + str(i) + " failed")
      time.sleep(1)

  if not succeeded:
      fail("polling did not succeed after 3 attempts")
```

## Current Limitations

### HTTP-Only Support

**Important:** Starlark control flow currently only works with HTTP/REST tests. Other protocol backends (MQTT, gRPC,
GraphQL) are not yet supported.

Attempting to use `run_stage()` - or `retry_until`/`fail_if` - with non-HTTP stages will raise a `NotImplementedError`.
The `if` key works with any backend, as it only sees test variables.

### Error Messages

Starlark error messages can be unhelpful when debugging failures. Error context may be limited, showing:

- `"Error evaluating starlark script"` without detailed stack traces
- `"Stage with id '<id>' not found"` without listing available stages
- Python exceptions wrapped without full traceback information

**Tips for debugging:**

1. Use `log()` statements to trace execution flow
2. Check stage IDs match exactly (case-sensitive)
3. Verify `control_flow` indentation (YAML multi-line strings)
4. Test regex patterns separately before using in scripts

### Type Restrictions

Starlark uses a JSON-serializable subset of Python types. Objects passed between Python and Starlark must be:

- Primitives: `str`, `int`, `float`, `bool`, `None`
- Collections: `dict` (with string keys), `list`, `tuple`
- Dataclasses (automatically converted to dicts)

Non-serializable objects (file handles, database connections, custom classes without `to_starlark()` method) can be
passed through to Starlark, but will be opaque and unusable.

## Starlark Language Reference

For complete language details, see
the [Starlark specification](https://github.com/bazelbuild/starlark/blob/master/spec.md).

Key differences from Python:

| Feature        | Python             | Starlark                                                  |
|----------------|--------------------|-----------------------------------------------------------|
| Classes        | Yes                | No user-defined classes (use `struct` to emulate classes) |
| Exceptions     | `try/except/raise` | No exception handling                                     |
| Comprehensions | Yes                | List + dict comprehensions only                           |
| Lambda         | Yes                | No                                                        |

## Examples

See the integration test files in `tests/integration/starlark/` for complete working examples of basic control flow,
includes, regex extraction, retry patterns, and the per-stage `if`/`retry_until` keys.

## Possible future improvements

- Add more library functions. Currently only `re` is available, starlark-go
  has [starlib](https://github.com/qri-io/starlib) which exposes a lot of useful functions (math, hashing, base64,
  etc).
- Support MQTT, gRPC, GraphQL. This becomes a bit more complicated with the new custom backend functionality.
- Make error messages more helpful.
- Add more helper functions (ensure JWT is valid, sleeping (time module?), etc).
    - Make this auto-export functions into either this document with mkdocstrings into
    - Let users import their own functions into starlark?
- Add a new CLI/ini flag to say "run 'finally' stages when using starlark script"
- Allow `if` on `finally` stages, and give it access to the previous stage's response.
- Make `re`/`time` and any other helper modules available in per-stage `if`/`retry_until` expressions - currently only
  the Starlark builtins and `struct` are in scope.
