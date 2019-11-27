#!/bin/sh

set -ex

tox -c tox-integration.ini -e py37-generic || true
tox -e py37 || true

coverage combine .coverage tests/integration/.coverage
coverage report -m
