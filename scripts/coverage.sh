#!/bin/sh

set -ex

# Runs the unit tests and the tests/integration suite in one top-level pytest
# run and reports combined coverage for tavern.
uv run pytest --cov tavern --cov-report=term-missing "$@"
