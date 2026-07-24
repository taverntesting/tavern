# Tests Knowledge Base

**Generated:** 2025-04-02

## Overview

Test suite split into unit tests (Python) and integration tests (YAML + Tavern).

## Structure

```
tests/
├── unit/             # Python unit tests
│   ├── test_core.py
│   ├── test_helpers.py
│   ├── plugins/      # Plugin-specific tests
│   └── tavern_grpc/  # gRPC-specific tests
└── integration/      # YAML-based integration tests
    ├── server.py     # Flask test server
    ├── conftest.py   # Integration test fixtures
    └── *.tavern.yaml # YAML test files
```

## Test Types

| Type | Location | Format |
|------|----------|--------|
| Unit | `unit/` | Python (.py) |
| Integration | `integration/` | YAML (.tavern.yaml) |

## Running Tests

```bash
# Unit tests
tox -q

# Integration tests (requires Docker)
tox -q -c tox-integration.ini

# Specific backend
tox -q -c tox-integration.ini -e py312-mqtt
```

## Mocking

- Use `with patch(...)` context managers
- Use `Mock(spec=...)` for type-safe mocks
- See `unit/conftest.py` for shared fixtures

## Notes

- Integration tests require Docker for backend services
- Each integration test file is a `.tavern.yaml` file
- Server is defined in `integration/server.py`
