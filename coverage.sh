#!/bin/sh

set -ex

tox -c tox-integration.ini -e py39-generic
tox -c tox-integration.ini -e py39-mqtt
tox -e py39 -r

coverage combine --append .coverage tests/integration/.coverage example/mqtt/.coverage
coverage report -m
