#!/usr/bin/env bash

set -ex

PYVER=3

# Separate as isort can interfere with other testenvs
tox --parallel -c tox.ini        \
  -e py${PYVER}check

tox --parallel -c tox.ini        \
  -e py${PYVER}       \
  -e py${PYVER}lint   \
  -e py${PYVER}mypy

tox -c tox-integration.ini  \
  -e py${PYVER}-generic     \
  -e py${PYVER}-advanced     \
  -e py${PYVER}-cookies     \
  -e py${PYVER}-components     \
  -e py${PYVER}-hooks     \
  -e py${PYVER}-mqtt
