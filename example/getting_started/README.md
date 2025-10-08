# Getting Started with Tavern

This directory contains examples to help you get started with Tavern quickly. Each example demonstrates a specific concept and includes a README explaining how to run it.

## Quick Start

1. **Install Tavern:**

   ```bash
   pip install tavern
   ```

2. **Run the simple example:**

   ```bash
   cd example/getting_started
   python -m pytest test_basic_api.tavern.yaml -v
   ```

3. **Start the test server (in another terminal):**

   ```bash
   python server.py
   ```

## Examples Overview

### Basic Examples

- **`test_basic_api.tavern.yaml`** - Your first Tavern test
- **`test_auth_flow.tavern.yaml`** - Authentication and session management
- **`test_error_handling.tavern.yaml`** - Testing error responses and edge cases

### Advanced Examples

- **`test_marks_and_fixtures.tavern.yaml`** - Using Pytest marks and fixtures
- **`test_parametrized_tests.tavern.yaml`** - Running the same test with different data
- **`test_external_functions.tavern.yaml`** - Custom validation and data generation

## What You'll Learn

- How to write your first YAML test
- How to handle authentication and sessions
- How to save and reuse data between requests
- How to use Pytest marks for test organization
- How to create custom validation functions
- How to handle errors and edge cases

## Next Steps

After running these examples, check out:

- `example/simple/` - More basic HTTP examples
- `example/advanced/` - Complex scenarios with JWT auth
- `example/mqtt/` - MQTT protocol examples
- `example/grpc/` - gRPC protocol examples

## Troubleshooting

**Common Issues:**

- **Port already in use:** Change the port in `server.py` and update the YAML files
- **Import errors:** Make sure you're in the right directory and have Tavern installed
- **Connection refused:** Make sure the test server is running

**Need Help?**

- Check the [Tavern documentation](https://tavern.readthedocs.io/)
- Look at the [examples directory](../) for more complex scenarios
- Open an issue on GitHub if you find a bug
