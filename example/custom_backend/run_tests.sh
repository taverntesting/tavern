#!/bin/bash

set -ex

if [ ! -d ".venv" ]; then
  uv venv
fi
. .venv/bin/activate

uv pip install -e . 'tavern @ ../..'

PYTHONPATH=. tavern-ci \
  --tavern-extra-backends=file=custom_backend \
  test_file_touched.tavern.yaml \
  --debug "$@" --stdout