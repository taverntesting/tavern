#!/bin/sh

set -ex

tox -c tox-integration.ini -e py38-generic
tox -c tox-integration.ini -e py38-mqtt
tox -e py38

coverage combine --append .coverage tests/integration/.coverage example/mqtt/.coverage
coverage report -m
