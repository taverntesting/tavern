# Contributing

All configuration for the project should be put into `pyproject.toml`.

## Working locally

1. Create a virtualenv using whatever method you like (
   eg, [virtualenvwrapper](https://virtualenvwrapper.readthedocs.io/))

1. Install dependencies from requirements.txt

## Running tests locally

To run a subset of the required tests, run the [smoke test script](/scripts/smoke.bash)

    ./scripts/smoke.bash

If on Windows, you should be able to just run the 'tox' commands in that file.

## Updating/adding a dependency

1. Add or update the dependency in [pyproject.toml](/pyproject.toml)

1. Update constraints and requirements file

```shell
uv pip compile --all-extras pyproject.toml --output-file constraints.txt -U
uv pip compile --all-extras pyproject.toml --output-file requirements.txt -U --generate-hashes
```

1. Run tests as above

## Pre-commit

Basic checks (formatting, import order) is done with pre-commit and is controlled by [the yaml file](/.pre-commit-config.yaml).

After installing dependencies, Run

    # check it works
    pre-commit run --all-files
    pre-commit install

Run every so often to update the pre-commit hooks

    pre-commit autoupdate

### Fixing Python formatting issue

    ruff format tavern/ tests/
    ruff --fix tavern/ tests/

### Fix yaml formatting issues

    pre-commit run --all-files

## Creating a new release

1. Setup `~/.pypirc`

1. Install the correct version of tbump

       pip install tbump@https://github.com/michaelboulton/tbump/archive/714ba8957a3c84b625608ceca39811ebe56229dc.zip

1. Tag and push to git with `tbump <new-tag> --tag-message "<tag-message>"`

1. Upload to pypi with `flit publish`

## Building the documentation

```shell
mkdir -p dist/
sphinx-build docs/source/ dist/
```