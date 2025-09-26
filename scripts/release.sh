#!/usr/bin/env bash

# Releasing:
# 1. tbump <new-version> --tag-message "<message>"
# 2. run this script

rm -rf build/ dist/ ./*.egg-info
fd pycache -u | xargs rm -rf

flit build   --format wheel --no-setup-py
flit publish --format wheel --no-setup-py --repository pypi
