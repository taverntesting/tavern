# Contributing

All configuration for the project should be put into `pyproject.toml`.

## Working locally

1. Create a virtualenv using whatever method you like (eg, [virtualenvwrapper](https://virtualenvwrapper.readthedocs.io/))

1. Install dependencies from requirements.txt

## Running tests locally

To run a subset of the required tests, run the [smoke test script](/scripts/smoke.bash)

    ./scripts/smoke.bash

If on Windows, you should be able to just run the 'tox' commands in that file.

## Updating/adding a dependency

1. Add or update the dependency in [pyproject.toml](/pyproject.toml)

1. Update requirements files (BOTH of them)

       pip-compile --output-file - --all-extras --resolver=backtracking pyproject.toml --reuse-hashes --generate-hashes > requirements.txt
       pip-compile --output-file - --all-extras --resolver=backtracking pyproject.toml --strip-extras > constraints.txt

1. Run tests as above

## Fixing formatting issue

    black tavern/ tests/
    isort --profile black tavern/ tests/
