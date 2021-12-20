#!/usr/bin/env bash

#./pants generate-lockfiles --resolve=black
./pants generate-lockfiles --resolve=coverage-py
./pants generate-lockfiles --resolve=isort
./pants generate-lockfiles --resolve=flake8
./pants generate-lockfiles --resolve=pylint
./pants generate-lockfiles --resolve=pytest
./pants generate-lockfiles --resolve=setuptools
