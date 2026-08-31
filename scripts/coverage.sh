#!/bin/sh

set -ex

tox -c tox-integration.ini -e py312-generic
tox -c tox-integration.ini -e py312-mqtt
tox -e py312

coverage combine --append .coverage tests/integration/.coverage example/mqtt/.coverage
coverage report -m
