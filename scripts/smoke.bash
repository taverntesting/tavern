#!/usr/bin/env bash

set -ex

pre-commit run ruff --all-files
pre-commit run black --all-files

# Separate as isort can interfere with other testenvs
tox --parallel -c tox.ini        \
  -e py3check

tox --parallel -c tox.ini        \
  -e py3       \
  -e py3mypy

tox -c tox-integration.ini  \
  -e py3-generic     \
  -e py3-advanced     \
  -e py3-cookies     \
  -e py3-components     \
  -e py3-hooks     \
  -e py3-mqtt
