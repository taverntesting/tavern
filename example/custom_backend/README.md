# Tavern Custom Backend Plugin

This example demonstrates how to create a custom backend plugin for Tavern, a pytest plugin for API testing. The custom
backend allows you to extend Tavern's functionality with your own request/response handling logic.

## Overview

This example plugin implements a simple file touch/verification system:

- `touch_file` stage: Creates or updates a file timestamp (similar to the Unix `touch` command)
- `file_exists` stage: Verifies that a specified file exists

## Implementation Details

This example includes:

- `Request` class: Extends `tavern.request.BaseRequest` and implements the `request_vars` property and `run()` method
- `Response` class: Extends `tavern.response.BaseResponse` and implements the `verify()` method
- `Session` class: Context manager for maintaining any state
- `get_expected_from_request` function: Optional function to generate expected response from request
- `jsonschema.yaml`: Schema validation for request/response objects
- `schema_path`: Path to the schema file for validation

## Entry Point Configuration

In your project's `pyproject.toml`, configure the plugin entry point:

```toml
[project.entry-points.tavern_your_backend_name]
my_implementation = 'your.package.path:your_backend_module'
```

Then when running tests, specify the extra backend:

```bash
pytest --tavern-extra-backends=your_backend_name
# Or, to specify an implementation to override the project entrypoint:
pytest --tavern-extra-backends=your_backend_name=my_other_implementation
```

Or the equivalent in pyproject.toml or pytest.ini. Note:

- The entry point name should start with `tavern_`.
- The key of the entrypoint is just a name of the implementation and can be anything.
- The `--tavern-extra-backends` flag should *not* be prefixed with `tavern_`.
- If Tavern detects multiple entrypoints for a backend, it will raise an error. In this case, you must use the second
  form to specify which implementation of the backend to use. This is similar to the build-in `--tavern-http-backend`
  flag.

This is because Tavern by default only tries to load "grpc", "http" and "mqtt" backends. The flag registers the custom
backend with Tavern, which can then tell [stevedore](https://github.com/openstack/stevedore) to load the plugin from the
entrypoint.

## Example Test

```yaml
---
test_name: Test file touched

stages:
  - name: Touch file and check it exists
    touch_file:
      filename: hello.txt
    file_exists:
      filename: hello.txt
```
