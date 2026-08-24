This file provides guidance to AI coding tools when working with code in this repository.

Tavern is a pytest plugin / CLI / library for testing APIs (HTTP, MQTT, gRPC, GraphQL) from YAML files.

## Environment and commands

All project configuration lives in `pyproject.toml` (see CONTRIBUTING.md).

```bash
uv venv
uv sync --all-extras --all-packages --all-groups   # after any dependency change
```

Unit tests (also doctests — `testpaths = ["tavern", "tests/unit"]` with `--doctest-modules`):

```bash
uv run pytest                                       # everything
uv run pytest tests/unit/test_core.py               # one file
uv run pytest tests/unit/test_core.py::TestFoo::test_bar
uv run tox -c tox.ini -e py3                        # as CI runs it
```

Lint/format/typecheck all go through pre-commit hooks (ruff, mypy, prettier, actionlint, uv-lock).
Use `prek` rather than `pre-commit` when it is installed — `scripts/smoke.bash` picks it automatically:

```bash
prek run --all-files          # == tox -e py3check
```

Integration tests need Docker; they spin up example servers via `docker compose` and run the real
`.tavern.yaml` files against them:

```bash
uv run tox -c tox-integration.ini -e py3-generic     # tests/integration
uv run tox -c tox-integration.ini -e py3-http        # example/http, likewise mqtt/grpc/graphql
```

`./scripts/smoke.bash` runs the whole set (lint + unit + all integration envs) and is the pre-PR check.
`example/custom_backend` has its own bats-based `run_tests.sh` exercising third-party plugin loading.

Releases: `tbump <new-tag>` (bumps `tavern/__init__.py`, regenerates CHANGELOG, re-locks) then `flit publish`.

## Architecture

### Entry points into a test run

Three front doors, all converging on `tavern._core.run.run_test`:

- **pytest plugin** (the main one) — registered via the `pytest11` entry point at `tavern._core.pytest`.
  `YamlFile` (`_core/pytest/file.py`) collects `test_*.tavern.yaml`, splitting each YAML document into
  a `YamlItem` (`_core/pytest/item.py`), a real `pytest.Item` that supports fixtures, marks and
  parametrization. `YamlItem.runtest()` is what calls `run_test`.
- **`tavern-ci` CLI** — `tavern/entry.py`, which just shells out to pytest.
- **library** — `tavern.core.run()`.

### Stage execution

`run_test` resolves stage `ref`s and `includes`, opens plugin "sessions" in an `ExitStack`, and hands each
stage to `_TestRunner.run_stage`, which layers on strictness, retries/delays and tinctures, then:
build request → compute expected response (before sending, since e.g. MQTT must subscribe first) →
run → verify → merge `save`d values back into the config variables for later stages.

`TestConfig` (`_core/pytest/config.py`) is the per-test state carried through all of this: variables,
strictness, selected backends. It is copied per test and per stage, so mutating a stage's config does not
leak upwards.

### Plugin system

Backends are stevedore entry points (`tavern_http`, `tavern_mqtt`, `tavern_grpc`, `tavern_graphql` in
`pyproject.toml`) — exactly one plugin may be enabled per backend. `_core/plugins.py` loads and caches them
and validates that each exposes: `session_type`, `request_type`, `request_block_name`, `verifier_type`,
`response_block_name`, `get_expected_from_request`, `schema`, `has_multiple_responses`. Adding a required
attribute here breaks every out-of-tree plugin, so it must go in the `required` list *and* the docs.

Each in-tree backend lives in `tavern/_plugins/<name>/` as `tavernhook.py` (the plugin class),
`request.py` (subclass of `tavern.request.BaseRequest`), `response.py` (subclass of
`tavern.response.BaseResponse`), plus a `jsonschema.yaml` that is merged into the core schema at
validation time.

### YAML loading and formatting

`_core/loader.py` defines a custom `IncludeLoader` with source-line tracking (used for error reporting)
and all the special tags: type sentinels for response matching (`!anyint`, `!anystr`, `!anything`,
`!re_match`/`!re_search`/`!re_fullmatch`, `!approx`), conversion tokens for requests (`!int`, `!bool`,
`!raw`), and include tags (`!include`, `!force_format_include`, `!force_original_structure`).

`_core/dict_util.py` does `{variable}` substitution (`format_keys`) and the recursive expected-vs-actual
comparison (`check_keys_match_recursive`), which is where the type sentinels are honoured and where
`StrictLevel` (`_core/strict_util.py`) decides whether extra keys are a failure.

### Schema validation

Test files are validated against `_core/schema/tests.jsonschema.yaml` with the enabled plugins' schemas
merged in (`_core/schema/files.py`). `tests.schema.yaml` is the older pykwalify schema, still used by
`tavern.helpers.validate_pykwalify` for validating *responses*.

### User-facing extension surface

- `tavern/helpers.py` — the functions users reference as `$ext` verifiers (`validate_jwt`,
  `validate_regex`, `validate_pydantic`, `check_jmespath_match`, ...). `_core/extfunctions.py` resolves
  `module:function` strings.
- `_core/pytest/newhooks.py` — the `pytest_tavern_beta_*` hooks. These are public API despite the
  `_core` path; changing a signature is a breaking change.

## Conventions

- Anything under `tavern/_core/` and `tavern/_plugins/` is private; the public API is `tavern/core.py`,
  `tavern/helpers.py`, `tavern/request.py`, `tavern/response.py`, `tavern/entry.py` and the beta hooks.
- Tests: unit tests in `tests/unit/` (pytest, Python). Anything that depends on the YAML format or needs a
  live server gets an integration test — add a flask endpoint in `tests/integration/server.py` and a
  `test_*.tavern.yaml` beside it.
- Generated protobuf files (`*_pb2.py`, `*_pb2.pyi`, `*_pb2_grpc.py`) are checked in and excluded from
  ruff/mypy; regenerate with `example/grpc/regenerate.sh` rather than editing them.
- New config belongs in `pyproject.toml`, not new dotfiles.
