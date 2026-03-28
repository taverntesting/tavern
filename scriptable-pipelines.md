# Scriptable Pipelines

## Background

Github actions has a way of defining a pipeline in a yaml file.
If you want some kind of 'optional' step, like "only run this step if a certain environment variable is set", or "Run
this step even if a previous step failed", you use special interpolation and a subset of functions:

```yaml
      - name: Install Protoc
        ## Install protoc only if we are building grpc
        if: ${{ contains(matrix.TOXENV, 'grpc') }}
        uses: arduino/setup-protoc@v3
        with:
          version: "23.x"
```

These `if` statements can get quite complex. It is also annoying to write conditional logic in an interpolated string.

We want to add similar functionality to Tavern, which currently only has a 'finally' block to properly support control
flow:

```yaml
---
test_name: Test finally block doing nothing

stages:
  - name: Simple echo
    request:
      url: "{global_host}/echo"
      method: POST
      json:
        value: "123"
    response:
      status_code: 200
      json:
        value: "123"

finally:
  - name: nothing
    request:
      url: "{global_host}/echo"
      method: POST
      json:
        value: "123"
```

## Starlark

To get around this, it would be nice to be able to write a pipeline in a language that is more expressive than yaml.

An example of starlark Python bindings:

```python
import starlark as sl

A_STAR = """
load("zz.star", "zz")
z = 3
z = 4

def f(x):
    z = 0
    for i in range(13):
        z += i*x
    return x*x - 5 + z

res = f(a - z + zz)

# Call a function defined in the module
g_res = g(123)
res
"""

glb = sl.Globals.standard()
mod = sl.Module()
mod["a"] = 5


def g(x: int):
    print(f"g called with {x}")
    return 2 * x


# Make the 'g' function callable from Starlark
mod.add_callable("g", g)

ast = sl.parse("a.star", A_STAR)


def load(name: str):
    if name == "zz.star":
        ast = sl.parse(name, "zz = 15")
        mod = sl.Module()
        sl.eval(mod, ast, glb)
        return mod.freeze()
    else:
        raise FileNotFoundError(name)


for lnt in ast.lint():
    print(lnt)
    print(lnt.severity)

val = sl.eval(mod, ast, glb, sl.FileLoader(load))
print(val)

print(mod["res"])
print(mod["g_res"])
```

## What we want

A way for people to write pipeline flow in starlark instead of in YAML.

Tavern supports referencing stages by id, like:

```yaml
stages:
  - type: ref
    id: my-stage
```

It may be easier to restrict this to only being able to reference stages by id.

### Requirements

1. Users write a starlark file and this is 'evaluated' to run a pipeline instead of jsut running each stage in sequence.
   The top level of the starlark file should have a function called `run_pipeline` which runs the pipeline, and should
   take a TestConfig object like in tavern/_core/pytest/config.py)
2. Some sensible functions are exposed in the starlark environment. For example `run_stage` to run a stage by id, using
   the code in tavern/_core/run.py. These functions return things that may be required for subsequent stages, such as
   the pass/fail state, tavern variables, etc.
3. As well as running `!include` to include other files, it uses the starlark `load` function to load other files (and
   maybe other functions?).
4. A new flag `--experimental-starlark-pipeline` is added to the CLI to enable this. If enabled, it looks for
   `*.tavern.star` files instead of `*.tavern.yaml`. Each of these files is still run as a single pytest test, allowing
   all the other pytest plugins to still work.
5. It would ideally be possible to 'render' each starlark file to a normal tavern yaml file, by replacing all the
   `run_stage` and other functions to a dummy function that just returns dummy values, but internally converts it to a
   representation which can be dumped into YAML.
6. All variable formatting must still work (though, as this is already done in Python it should be transparent).

A sketch of what a starlark pipeline file might look like:

```yaml
# stages.yaml
---
stages:
  - id: get-cookie
    name: Get tavern-cookie-1
    request:
      url: "{host}/get_cookie"
      method: POST
      json:
        cookie_name: tavern-cookie-1
    response:
      status_code: 200
      cookies:
        - tavern-cookie-1
  - id: typetoken-anything-match
    name: match top level
    request:
      url: "{host}/fake_dictionary"
      method: GET
    response:
      status_code: 200
      json: !anything
```

```python
def run_pipeline(ctx):
    # "include" is a starlark function which loads a file and returns the contents as a dict
    config_file = include("stages.yaml")
    stages = config_file["stages"]
    stages_by_id = {stage["id"] for stage in stages}

    # ctx is the updated TestConfig object
    ctx, _ = run_stage(ctx, stages_by_id["get-cookie"])

    # Run until we get a response that matches the expected response
    for i in range(10):
        ctx, resp = run_stage(ctx, stages_by_id["typetoken-anything-match"])
        if resp.success:
            print(resp.response["json"])
            return

    # "fail" is a builtin starlark function which instantly causes execution to stop
    fail("test did not pass")
```

### Control flow

Starlark doesn't have 'exceptions' so we'll just use the `fail` function to stop execution. This lets users control when
to fail tests. It lets them do things like:

```python
def finalize(ctx):
    ctx, resp = run_stage(ctx, {"request": {"json": ..., "url": "http://localhost:8080/cleanup"}})


def run_pipeline(ctx):
    ...
    ctx, resp = run_stage(ctx, {"request": {"json": ..., "url": "http://localhost:8080/login"}})
    if resp.failure:
        finalize(ctx)
        fail("test did not pass")

    ctx, resp = run_stage(ctx, {"request": {"json": ..., "url": "http://localhost:8080/run"}})
    ...
```

### Fixtures

Like Tavern does currently, when these starlark files are loaded, before tests are run, fixtures are loaded.

This YAML Tavern test:

```yaml
---
test_name: Test multiple parametrized values

includes:
  - !include common.yaml

marks:
  - parametrize:
      key: fruit
      vals:
        - apple
        - orange
        - pear
  - parametrize:
      key: edible
      vals:
        - rotten
        - fresh
        - unripe

stages: [ ... ]
```

Currently results in 6 tests being run. There MUST be some way of exposing this in starlark, either by having an
explicit `setup_fixtures()` function, having a top level function in the starlark file called `setup_fixtures()`, or
some other way that makes sense.

### Marks

Similar to fixtures, there should be some way of marking tests in starlark. YAML example:

```yaml

---
test_name: Test mark with keyword arguments

includes:
  - !include common.yaml

marks:
  - my_cool_mark
  - skipif(True, reason='Testing keyword arguments in marks')
```

This marks the test with `skipif` and it's skipped if the condition is true. It also marks it with `my_cool_mark` so
that a user can do `pytest -m my_cool_mark` to run this test.

This might also be a top level function in the starlark file called `setup_marks()` which is called before tests are
run.

### Starlark stages

Because starlark does let you define a dict, stages can also just be defined directly in the starlark file (even if it
will get messy). eg

```python
# stages.star
stages = {
    "get-cookie": {"name": "get-cookie", "url": "https://example.com", "json": {...}}
}

# my_test.tavern.star
stages = include("stages.star")


def run_pipeline(ctx):
    ctx, resp = run_stage(ctx, stages["get-cookie"])
    ...
```

## Notes

- Starlark spec: https://github.com/google/starlark-go/blob/master/doc/spec.md This is almost identical to python.
- The way starlark-python works, all objects must be serialised to JSON before being passed to any function.
- POSSIBLE EXTENSION: Allow users to register their own functions in the starlark environment. This would allow users to
  write their own functions to do things like 'fetch a token' but it introduces a security risk.

## Edge Cases and Implementation Details

### Response Object

The `run_stage` function returns a response object with the following structure:

```python
@dataclasses.dataclass
class StageResponse:
    """Response from running a stage"""
    success: bool  # True if all verifications passed
    failure: bool  # True if any verification failed
    response: dict  # The response body/headers/cookies
    request_vars: dict  # Any variables captured during the request
```

### TestConfig Object

The `TestConfig` object passed to `run_pipeline` has the following structure (from `tavern/_core/pytest/config.py`):

```python
@dataclasses.dataclass(frozen=True)
class TestConfig:
    variables: dict  # Available format variables
    strict: StrictLevel  # Strictness setting for response validation
    follow_redirects: bool  # Whether to follow HTTP redirects
    stages: list  # Available stages from includes
    tavern_internal: TavernInternalConfig  # Internal tavern config
```

### Fixtures and Marks

Fixtures are handled before `run_pipeline` is called. The starlark environment should provide:

1. `setup_fixtures()` - Optional function called before pipeline execution to set up any pytest fixtures
2. `setup_marks()` - Optional function that can return marks to be applied to the test

### File Loading

The `include` function loads YAML files and returns them as dictionaries. This uses the same `load_single_document_yaml`
function from `tavern/_core/loader.py`.

The `load` function is the standard starlark module loading mechanism and can be used to load other `.star` files.

### Variable Formatting

All variable formatting (`{variable}` syntax) happens transparently in Python before the stage runs. The `run_stage`
function receives a dictionary that has already had formatting applied.

### Error Handling

If a stage fails (verification does not match), the `StageResponse.failure` will be `True`. It is up to the user's
starlark code to decide whether to continue or call `fail()` to stop execution.

The `fail` function is a builtin that stops execution immediately with an optional message.

### YAML Stage Format

Stages can be defined directly in YAML files loaded via `include`, or inline in the starlark code. Each stage must have:

- `id`: Unique identifier for the stage (used for `type: ref` stages)
- `name`: Human-readable name
- `request`: Request specification (url, method, headers, json, etc.)
- `response`: Response validation (status_code, cookies, json, etc.)

### Limitations

1. **No exceptions in Starlark**: Starlark does not have exceptions. Use the `fail()` function to stop execution.
2. **JSON serialization**: All objects passed to starlark functions must be JSON-serializable.
3. **Single-threaded**: Starlark is single-threaded; no parallel stage execution.
4. **No arbitrary Python**: Only exposed functions are available in the starlark environment. 