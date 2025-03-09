#!/bin/sh

set -ex

tox -c tox-integration.ini -e py310-generic
tox -c tox-integration.ini -e py310-mqtt
tox -e py310

coverage combine --append .coverage tests/integration/.coverage example/mqtt/.coverage
coverage report -m
