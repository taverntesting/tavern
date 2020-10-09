#!/usr/bin/env bash

set -ex

PYVER=39

fd pycache -u | xargs rm -rf

tox --parallel -c tox.ini        \
  -e py${PYVER}flakes

tox --parallel -c tox.ini        \
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
