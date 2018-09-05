#!/bin/sh

set -ex

tox -c tox-integration.ini -e py36-generic
tox -e py36

coverage combine .coverage tests/integration/.coverage
coverage report -m
