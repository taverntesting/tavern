#!/usr/bin/env bash

set -ex

PYVER=37

tox -c tox.ini -e py${PYVER}flakes
tox -c tox.ini -e py${PYVER}
tox -c tox.ini -e py${PYVER}lint

tox -c tox-integration.ini -e py${PYVER}-generic
tox -c tox.ini -e py${PYVER}black
