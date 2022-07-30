#!/usr/bin/env bash

set -ex

PYVER=39

tox -c tox.ini        \
  -e py${PYVER}flakes

tox -c tox.ini        \
  -e py${PYVER}       \
  -e py${PYVER}-pytest6       \
  -e py${PYVER}black  \
  -e py${PYVER}lint   \
  -e py${PYVER}mypy

tox -c tox-integration.ini  \
  -e py${PYVER}-generic     \
  -e py${PYVER}-advanced     \
  -e py${PYVER}-components     \
  -e py${PYVER}-mqtt
