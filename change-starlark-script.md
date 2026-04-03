The starlark integration should be changed so that the test stages are still loaded from a yaml file, but the actual
order of text execution can be defined in an inline starlark script.

Example of existing yaml test:

```yaml
test_name: Do something with stages

includes:
  # Contains stages with an 'id'
  - !include common.yaml

stages:
  # Assume this stage saves the auth header value to a variable called 'auth_header_val'
  - type: ref
    id: login
  - type: ref
    id: get_user_id
  - name: make request with headers
    # Skip this stage if the user id is 0
    skip: "{user_id} == 0"
    request:
      url: "http://localhost:8000/api/v1/users/me"
      json:
        name: "John Doe"
      headers:
        Authorization: "{auth_header_val}"
    response:
      status_code: 200
  - name: update user
    # retry this stage 3 times if it fails
    max_retries: 3
    request:
      url: "http://localhost:8000/api/v1/users/update"
      method: POST
      json:
        name: "John Smith"
      headers:
        Authorization: "{auth_header_val}"
    response:
      status_code: 200
```

Now imagine how this might be defined with starlark

```yaml
test_name: Do something with stages

includes:
  # Contains stages with an 'id'
  - !include common.yaml

stages:
  # Assume this stage saves the auth header value to a variable called 'auth_header_val'
  - type: ref
    id: login
  - type: ref
    id: get_user_id
  - name: make request with headers
    # Normally stages don't have IDs inline, but needed for starlark
    id: make_request_with_headers
    request:
      ...
    response:
      ...
  - name: update user
    id: update_user
    request:
      ...
    response:
      ...

# This is the starlark script that defines the order of execution
# control_flow is a placeholder name, could be changed to something more obvious?
control_flow: |
  # run_stage is a function that runs a stage by name. stages are loaded by id, and then exposed as global variables
  # that starlark can use to avoid having to do something like 'stages["make_request_with_headers"]'
  resp = run_stage("make_request_with_headers")
  # resp is a starlark object that has a 'failed' attribute and a 'status_code' attribute
  if resp.status_code == 401:
      # If it was a 401 error, just login
      run_stage("login")
  elif resp.failed:
      # fail is the starlark builtin function that fails the test
      fail("Failed to make request")

  # skip the update user stage if the user id is 0
  if resp["user_id"] != 0:
      # run 3 retries
      for i in range(3):
          resp = run_stage("update_user")
          # Allows granular control over the retry logic
          if resp.status_code == 429:
              continue
          elif resp.status_code == 200:
              break
          else:
              fail("Failed to update user")

```

Things that need doing for this to work:

### Load stages by id in starlark script

Load all stages by id in the current test and inject a global variable for each stage into the starlark module
environment, eg

```python
# Python side
# Create the starlark module
module = starlark.Module()

# stages is a list of stages, with an id
module["_stages"] = stages
module.add_callable("_run_stage", self._run_stage)

# Parse the script
dialect = Dialect.extended()

ast = starlark.parse(str(self.test_path), script, dialect=dialect)
```

Also modify run_stage so it is in starlark wrapping the python function and can load the stage by id easily:

```python
# starlark side
_loaded_stages = {
    # Loads from global variable
    stage.id: stage for stage in _stages
}


def run_stage(stage_id):
    stage = _loaded_stages[stage_id]
    # Call python function from starlark to run the stage
    ... = _run_stage(stage, test_config, ...)
```

### Returning results in a nice format

Currently the run_stage can only return a
dict because of the way the starlark and python integration works, so it would need to be something like:

```python
# Python side
def run_stage(stage_name):
    try:
        response = _run_stage(stage, test_config, sessions)
    except Exception as e:
        logger.exception("Failed to run stage")
        raise exceptions.StarlarkError("Failed to run stage") from e
    # Create a new context with updated test_config
    # This ensures Starlark sees the updated state
    new_ctx = to_starlark(
        {
            "test_config": test_config,
            "sessions": sessions,
        }
    )
    return new_ctx, response
```

```python
# starlark side
def run_stage(stage_id):
    ...
    # resp is a dict.
    resp = _run_stage(stage, test_config, sessions)

    # Convert the dict to a starlark object
    return struct(
        status_code=resp["status_code"],
        failed=resp["status_code"] >= 400,
        # Any other fields that should be exposed to starlark, which would be useful for testing. Possibly:
        # - response body loaded as json (could be a dict, or list, or string)
        # - variables (some may be opaque and unusable!)
        resp=resp,
    )
```

### Removal of 'ctx'

The current code uses a 'ctx' variable to pass around the test config and sessions, this can be removed as this side of
it should all be handles in Python. Starlark is just a script controlling the execution of the test.

## Implementation

The place this is all controlled from would be in tavern/_core/run.py, instead of having to define a separate pytest
entrypoint, test runner, etc.

1. Final Goal: Refactor the Starlark integration in the Tavern testing framework so that:
    - Test stages are loaded from YAML files as usual (via normal Tavern YAML loading)
    - A new control_flow field in the YAML contains an inline Starlark script
    - Stages with id fields are automatically injected as global variables in the Starlark module
    - run_stage(stage_id) is callable by string ID — no need to pass full stage dicts or context
    - Results returned as a nice object with status_code, failed, etc.
    - Remove the ctx (PipelineContext) parameter — Starlark just controls execution flow, Python handles all state
    - Entry point is in tavern/_core/run.py instead of a separate pytest entrypoint

2. Work Completed:
    - Phase 1 (DONE): Added control_flow field to tests.schema.yaml as optional string field, and also added missing
      finally field
    - Codebase exploration (DONE): Read all starlark files, run.py, schema files, test files, AGENTS.md files

3. Remaining Tasks
    - Phase 2-5 (IN PENDING): Refactor starlark_env.py
    - Phase 6 (PENDING): Integrate with run.py — detect control_flow field in test spec, delegate to
      StarlarkPipelineRunner instead of sequential stage execution
    - Phase 7 (PENDING): Create new integration test YAML file with control_flow
    - Phase 8 (PENDING): Update existing test_basic_pipeline.tavern.star to new YAML+control_flow format
    - Phase 9 (PENDING): Run unit tests and verify no regressions
    - Phase 10 (PENDING): Run integration tests and manual QA verification
