#!/bin/bash

set -ex

if [ ! -d ".venv" ]; then
  uv venv
fi
. .venv/bin/activate

uv sync

if ! command -v bats; then
  exit 1
fi

# Run tests using bats
bats --timing --print-output-on-failure "$@" tests.bats
