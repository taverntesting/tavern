# Contributing

## Running tests locally

To run a subset of the required tests, run the [smoke test script](/scripts/smoke.bash)

    ./scripts/smoke.bash

## Updating/adding a dependency

1. Add or update the dependency in [pyproject.toml](/pyproject.toml)

1. Update requirements files (BOTH of them)

       pip-compile --output-file - --all-extras --resolver=backtracking pyproject.toml --generate-hashes > requirements.txt
       pip-compile --output-file - --all-extras --resolver=backtracking pyproject.toml --strip-extras > constraints.txt

1. Run tests

       ./scripts/smoke.bash

## Fixing formatting issue

    black tavern/ tests/
    isort --profile black tavern/ tests/
