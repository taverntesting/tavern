#!/usr/bin/env bash

set -ex

PYVER=38

tox -c tox.ini        \
  -e py${PYVER}flakes \
  -e py${PYVER}       \
  -e py${PYVER}black  \
  -e py${PYVER}lint

tox -c tox-integration.ini  \
  -e py${PYVER}-generic     \
  -e py${PYVER}-mqtt
