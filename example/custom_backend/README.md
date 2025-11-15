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
[project.entry-points.'tavern.plugins.backends']
your_backend_name = 'your.package.path:your_backend_module'
```

Then when running tests, specify the extra backend:

```bash
pytest --tavern-extra-backends=your_backend_name=your.package.path:your_backend_module
```

Or in your `pytest.ini`:

```ini
[tool:pytest]
tavern-extra-backends = your_backend_name=your.package.path:your_backend_module
```

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
