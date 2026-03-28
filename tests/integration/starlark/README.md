# Starlark Pipeline Integration Tests

This folder contains integration tests for the scriptable pipelines feature using Starlark.

## Prerequisites

1. The test server must be running (see `tests/integration/server.py`)
2. Docker must be available (integration tests run in containers)

## Running the Tests

To run the starlark integration tests, you need to enable the experimental flag:

```bash
# Start the test server (from tests/integration directory)
docker-compose up -d server

# Run the starlark tests with the experimental flag
tox -q -c tox-integration.ini -e py311 -- --tavern-experimental-starlark-pipeline tests/integration/starlark/
```

Or using pytest directly:

```bash
# Starting server in background
cd tests/integration && docker-compose up -d

# Run tests
pytest --tavern-experimental-starlark-pipeline tests/integration/starlark/ -v

# Cleanup
docker-compose down
```

## Test Files

- `test_basic_pipeline.tavern.star` - Basic pipeline test using include and run_stage
