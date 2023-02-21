#!/usr/bin/env bash

# Releasing:
# 0. pip install tbump@https://github.com/michaelboulton/tbump/archive/714ba8957a3c84b625608ceca39811ebe56229dc.zip -c constraints.txt
# 1. tbump <new-version> --tag-message "<message>"
# 2. run this script

rm -rf build/ dist/ ./*.egg-info
fd pycache -u | xargs rm -rf

flit build   --format wheel --no-setup-py
flit publish --format wheel --no-setup-py --repository pypi
