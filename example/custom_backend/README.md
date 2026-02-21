# Tavern Custom Backend Plugin

This example demonstrates how to create a custom backend plugin for Tavern, a pytest plugin for API testing.
Custom backends allows you to extend Tavern's functionality with your own request/response handling logic.

## Overview

This example plugin implements a simple file touch/verification system:

- `touch_file` stage: Creates or updates a file timestamp (similar to the Unix `touch` command)
- `file_exists` stage: Verifies that a specified file exists

## Implementation Details

The basic operation of plugins is described in the [plugin documentation](https://tavern.readthedocs.io/en/stable/plugins/).

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
