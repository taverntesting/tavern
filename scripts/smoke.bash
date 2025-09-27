#!/usr/bin/env bash

set -ex

uv lock --check || true
pre-commit run ruff-check --all-files || true
pre-commit run ruff-format --all-files || true

tox --parallel -c tox.ini        \
  -e py3check

tox --parallel -c tox.ini        \
  -e py3

tox -c tox-integration.ini  \
  -e py3-generic,py3-grpc,py3-mqtt
