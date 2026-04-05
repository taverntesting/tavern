#!/usr/bin/env bash

set -ex

# Use prek if available, otherwise default to pre-commit
if command -v prek >/dev/null 2>&1; then
    PRE_COMMIT_CMD="prek"
else
    PRE_COMMIT_CMD="pre-commit"
fi

uv lock --check || true
$PRE_COMMIT_CMD run ruff-check --all-files || true
$PRE_COMMIT_CMD run ruff-format --all-files || true

TOX_CMD="uv run tox"

$TOX_CMD --parallel -c tox.ini        \
  -e py3check

$TOX_CMD --parallel -c tox.ini        \
  -e py3

$TOX_CMD -c tox-integration.ini  \
  -e py3-graphql,py3-generic,py3-http,py3-grpc,py3-mqtt
