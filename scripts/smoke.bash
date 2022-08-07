#!/usr/bin/env bash

set -ex

black tavern tests
isort --profile black tavern tests/

PYVER=39

tox --parallel -c tox.ini        \
  -e py${PYVER}flakes \
  -e py${PYVER}       \
  -e py${PYVER}-pytest6       \
  -e py${PYVER}black  \
  -e py${PYVER}lint   \
  -e py${PYVER}mypy

tox -c tox-integration.ini  \
  -e py${PYVER}-generic     \
  -e py${PYVER}-advanced     \
  -e py${PYVER}-cookies     \
  -e py${PYVER}-components     \
  -e py${PYVER}-hooks     \
  -e py${PYVER}-mqtt
