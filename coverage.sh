#!/bin/sh

set -ex

tox -c tox-integration.ini -e py38-generic
tox -e py38

coverage combine --append .coverage tests/integration/.coverage
coverage report -m
