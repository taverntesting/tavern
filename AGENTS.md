# Tavern Knowledge Base

**Generated:** 2025-04-02
**Language:** Python
**Type:** Pytest Plugin for API Testing

## Overview

Tavern is a pytest plugin, command-line tool, and Python library for automated testing of RESTful APIs, MQTT-based APIs, and gRPC services. Uses YAML-based test syntax.

## Structure

```
tavern/
├── tavern/           # Main package
│   ├── _core/        # Core logic (pytest integration, schema, loader)
│   ├── _plugins/     # Protocol backends (rest, mqtt, grpc, graphql)
│   ├── entry.py      # CLI entry point (tavern-ci command)
│   ├── core.py       # Core test execution
│   ├── request.py    # Request abstractions
│   └── response.py   # Response abstractions
├── tests/            # Unit and integration tests
├── example/          # Workspace examples (mqtt, grpc, http, graphql)
├── scripts/          # Development scripts
├── pyproject.toml    # Project configuration
├── tox.ini           # Unit test configuration
└── tox-integration.ini  # Integration test configuration
```

## Where to Look

| Task | Location | Notes |
|------|----------|-------|
| CLI entry | `tavern/entry.py` | `tavern-ci` command implementation |
| Test execution | `tavern/_core/run.py` | Main test runner logic |
| Pytest integration | `tavern/_core/pytest/` | Pytest plugin, hooks, file handling |
| REST plugin | `tavern/_plugins/rest/` | HTTP/REST backend |
| MQTT plugin | `tavern/_plugins/mqtt/` | MQTT backend |
| gRPC plugin | `tavern/_plugins/grpc/` | gRPC backend |
| GraphQL plugin | `tavern/_plugins/graphql/` | GraphQL backend |
| Schema validation | `tavern/_core/schema/` | JSON schema validation |
| Unit tests | `tests/unit/` | Python-based unit tests |
| Integration tests | `tests/integration/` | YAML-based integration tests |

## Entry Points

- **CLI:** `tavern/entry.py` → `tavern-ci` command
- **Pytest:** `tavern._core.pytest` entry point
- **Starlark:** `tavern._core.starlark` entry point
- **HTTP Plugin:** `tavern._plugins.rest.tavernhook:TavernRestPlugin`

## Code Map

| Symbol | Type | Location | Purpose |
|--------|------|----------|---------|
| `main()` | function | `tavern/entry.py:41` | CLI entry point |
| `run()` | function | `tavern/_core/run.py` | Test execution |
| `YamlItem` | class | `tavern/_core/pytest/item.py` | Pytest test item |
| `PluginHelperBase` | class | `tavern/_core/plugins.py` | Plugin base class |
| `TavernRestPlugin` | class | `tavern/_plugins/rest/tavernhook.py` | REST backend plugin |

## Conventions

- Use **dataclasses** and **type annotations** whenever possible
- Use **Google-style docstrings**
- Use **`with patch(...):`** context managers (NOT `@patch` decorators)
- Use **Mock(spec=...)** to ensure mocks have correct interface
- Add dependencies to `pyproject.toml`, then run `uv lock --upgrade && uv sync --all-extras`

## Anti-Patterns

- **NEVER** use `@patch` decorators - always use `with patch(...):` context managers
- **NEVER** suppress type errors with `as any`, `@ts-ignore`
- **NEVER** commit without explicit request
- **NEVER** leave code in broken state after failures

## Commands

```bash
# Run unit tests
tox -q

# Run specific test file
tox -q -e py312 -- -qq tests/unit/plugins/graphql/

# Run integration tests
tox -q -c tox-integration.ini -e py312 -- -qq

# Install dependencies
uv sync --all-extras

# Update lock file
uv lock --upgrade

# Run smoke checks
./scripts/smoke.bash
```

## Notes

- Entry point defined in `pyproject.toml`: `tavern-ci = "tavern.entry:main"`
- Pytest entry points: `tavern`, `tavern_starlark`
- HTTP plugin entry point: `requests = "tavern._plugins.rest.tavernhook:TavernRestPlugin"`
- Uses **uv** for dependency management (not pip)
- Uses **tox** for testing (two configs: tox.ini for unit, tox-integration.ini for integration)
- Workspace members in `example/` directory (mqtt, grpc, http, graphql)
