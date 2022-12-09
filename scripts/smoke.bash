#!/usr/bin/env bash

set -ex

PYVER=310

tox -c tox.ini        \
  -e py${PYVER}flakes \
  -e py${PYVER}       \
  -e py${PYVER}black  \
  -e py${PYVER}lint   \
  -e py${PYVER}mypy

tox -c tox-integration.ini  \
  -e py${PYVER}-generic     \
  -e py${PYVER}-advanced     \
  -e py${PYVER}-components     \
  -e py${PYVER}-mqtt
