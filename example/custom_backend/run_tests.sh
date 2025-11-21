#!/bin/bash

set -ex

if [ ! -d ".venv" ]; then
  uv venv
fi
. .venv/bin/activate

uv pip install -e . 'tavern @ ../..'

PYTHONPATH=. tavern-ci \
  --tavern-extra-backends=file \
  --debug "$@" --stdout \
  tests

PYTHONPATH=. tavern-ci \
  --tavern-extra-backends=file=my_tavern_plugin \
  --debug "$@" --stdout \
  tests

PYTHONPATH=. tavern-ci \
  --tavern-extra-backends=file=i_dont_exist \
  --debug "$@" --stdout \
  tests
