#!/bin/sh

set -ex

tox -c tox-integration.ini -e py37-generic
tox -e py37

coverage combine .coverage tests/integration/.coverage
coverage report -m
