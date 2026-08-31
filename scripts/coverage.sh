#!/bin/sh

set -ex

# Runs the unit tests and the tests/integration suite in one top-level pytest
# run and reports combined coverage for tavern. The integration yaml files run
# in pytest subprocesses (see tests/integration/test_run_integration_suite.py),
# which are measured too via 'patch = ["subprocess"]' + 'parallel = true' in
# pyproject.toml; pytest-cov combines the parallel data files automatically.
uv run pytest --cov tavern --cov-report=term-missing "$@"
