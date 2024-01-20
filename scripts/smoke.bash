#!/usr/bin/env bash

set -ex

pre-commit run ruff --all-files
pre-commit run ruff-format --all-files

# Separate as isort can interfere with other testenvs
tox --parallel -c tox.ini        \
  -e py3check

tox --parallel -c tox.ini        \
  -e py3,py3mypy

tox -c tox-integration.ini  \
  -e py3-generic,py3-grpc,py3-mqtt
