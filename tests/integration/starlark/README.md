# Starlark Pipeline Integration Tests

This folder contains integration tests for the scriptable pipelines feature using Starlark.

## Prerequisites

1. The test server must be running (see `tests/integration/server.py`)
2. Docker must be available (integration tests run in containers)

## Running the Tests

To run the starlark integration tests, you need to enable the experimental flag:

```bash
# Start the test server (from tavern root directory)
cd tests/integration && docker-compose up -d server

# Run the starlark tests with the experimental flag
tox -q -c tox-integration.ini -e py312 -- --tavern-experimental-starlark-pipeline tests/integration/starlark/
```

Or using pytest directly:

```bash
# Starting server (from tavern root directory)
docker-compose -f tests/integration/docker-compose.yml up -d server

# Run tests (from tavern root directory)
pytest --tavern-experimental-starlark-pipeline tests/integration/starlark/ -v

# Cleanup
docker-compose -f tests/integration/docker-compose.yml down
```

## Test Files

- `test_control_flow_inline.tavern.yaml` - Basic pipeline test
