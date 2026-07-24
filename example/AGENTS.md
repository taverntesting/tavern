# Examples Knowledge Base

**Generated:** 2025-04-02

## Overview

Workspace examples demonstrating Tavern usage with different protocols. Each is a uv workspace member.

## Structure

```
example/
├── mqtt/             # MQTT example
│   ├── tavern_mqtt_example/
│   └── tests/
├── grpc/             # gRPC example
│   ├── tavern_grpc_example/
│   └── tests/
├── http/             # HTTP/REST example
│   ├── tavern_http_example/
│   └── tests/
└── graphql/          # GraphQL example
    ├── tavern_graphql_example/
    └── tests/
```

## Workspace Members

Configured in `pyproject.toml`:

```toml
[tool.uv.workspace]
members = [
    "example/mqtt",
    "example/grpc",
    "example/http",
    "example/graphql",
]
```

## Running Examples

```bash
# HTTP example
cd example/http
tox -e py312

# Or use pytest directly
pytest tests/
```

## Each Example Contains

- Server implementation (Flask/gRPC/etc.)
- Tavern YAML tests (.tavern.yaml)
- Configuration (pyproject.toml)

## Notes

- Examples are standalone uv workspace members
- Can be installed independently: `uv pip install -e example/http/`
- Tests demonstrate protocol-specific features
