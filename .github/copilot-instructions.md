# Tavern AI Coding Agent Instructions

This guide enables AI coding agents to be productive in the Tavern codebase. It summarizes architecture, workflows, conventions, and integration points unique to Tavern.

## Big Picture Architecture
- **Tavern** is a pytest plugin, CLI tool, and Python library for automated API testing using YAML-based test files.
- Supports both **RESTful** and **MQTT** APIs. Key logic lives in `tavern/` (core, request, response, helpers) and `_core/`, `_plugins/` for extensibility.
- Example setups (HTTP, MQTT, cookies, gRPC, etc.) are in `example/` and `components/`—useful for integration and advanced usage patterns.
- Tests are organized in `tests/unit/` (Pytest-based unit tests) and `tests/integration/` (integration tests, often using Dockerized servers).

## Developer Workflows
- **Run all tests:**
  - Unit: `tox` (requires `tox` installed)
  - Integration: `tox -c tox-integration.ini` (requires Docker)
  - Individual YAML tests: `pytest test_*.tavern.yaml`
- **MQTT/HTTP integration examples:**
  - Start services: `docker compose up --build` in relevant example/component folder
  - Run tests: `pytest` in another terminal
- **Formatting:**
  - Use `ruff format` for code style. Enable pre-commit hook: `pre-commit install`
- **Dependencies:**
  - Install with `pip install -r requirements.txt` for development

## Project-Specific Conventions
- **Test files:** Must be named `test_*.tavern.yaml` for Pytest discovery.
- **YAML test structure:** Each file contains one or more tests, each with one or more stages (request/response pairs).
- **Custom validation:** Utility functions and plugins live in `_core/`, `_plugins/`, and can be referenced in YAML tests.
- **Integration tests:** Use Docker containers for realistic server setups. See `example/` and `components/` for patterns.
- **Logging/config:** See `tests/logging.yaml` and example configs for customizing output and test environments.

## Integration Points & External Dependencies
- **Pytest**: Main test runner and plugin system.
- **Docker**: Used for integration tests and example environments.
- **MQTT**: Uses `paho-mqtt` for message passing; see `example/mqtt/` for setup.
- **HTTP**: Uses `requests` for HTTP requests.
- **YAML**: Test syntax and schema validation via `pyyaml` and `pykwalify`.
- **Other**: JWT handling (`pyjwt`), colorized logs (`colorlog`).

## Key Files & Directories
- `tavern/`: Core implementation (entry, core, helpers, request, response)
- `example/`, `components/`: Advanced and integration examples
- `tests/unit/`, `tests/integration/`: Test suites
- `requirements.txt`, `tox.ini`, `tox-integration.ini`: Dependency and test configs
- `README.md`, `docs/`: High-level documentation and usage

## Patterns & Examples
- **Multi-stage tests:** See YAML files in `example/` for chaining requests/responses.
- **MQTT listener/server:** See `example/mqtt/` for Docker Compose, server, and listener patterns.
- **Custom plugins:** Extend via `_plugins/` and reference in YAML.

---

For more details, see [README.md](../README.md) and [docs/](../docs/).

---

**Feedback:** If any section is unclear or missing, please specify which workflows, conventions, or architectural details need further explanation.
