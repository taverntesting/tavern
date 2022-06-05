#!/usr/bin/env bash

rm -rf build/ dist/ ./*.egg-info
fd pycache -u | xargs rm -rf

python setup.py bdist_wheel
twine upload -r pypi dist/*.whl
