#!/bin/sh

set -ex

tox -c tox-integration.ini -e py311-generic
tox -c tox-integration.ini -e py311-mqtt
tox -e py311

coverage combine --append .coverage tests/integration/.coverage example/mqtt/.coverage
coverage report -m
