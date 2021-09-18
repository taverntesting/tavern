#!/usr/bin/env bash

set -ex

PYVER=39

tox -c tox.ini        \
  -e py${PYVER}flakes \
  -e py${PYVER}       \
  -e py${PYVER}black  \
  -e py${PYVER}lint   \
  --parallel

tox -c tox-integration.ini  \
  -e py${PYVER}-generic     \
  -e py${PYVER}-mqtt
