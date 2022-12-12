#!/usr/bin/env bash

rm -rf build/ dist/ ./*.egg-info
fd pycache -u | xargs rm -rf

flit build   --format wheel --no-setup-py
flit publish --format wheel --no-setup-py --repository pypi
