# Contributing

All configuration for the project should be put into `pyproject.toml`.

## Working locally

1. Create a virtualenv using whatever method you like (
   eg, [virtualenvwrapper](https://virtualenvwrapper.readthedocs.io/))

```shell
uv venv
```

1. Sync venv

```shell
uv sync --all-extras --all-packages --all-groups
```

## Running tests locally

To run a subset of the required tests, run the [smoke test script](/scripts/smoke.bash)

    ./scripts/smoke.bash

If on Windows, you should be able to just run the 'tox' commands in that file.

## Updating/adding a dependency

1. Add or update the dependency in [pyproject.toml](/pyproject.toml)

1. Update lock file

```shell
uv lock --upgrade
```

1. Sync venv

```shell
uv sync --all-extras --all-packages --all-groups
```

1. Run tests as above

## Pre-commit

Basic checks (formatting, import order) are done with pre-commit and are controlled
by [the yaml file](/.pre-commit-config.yaml).

After installing dependencies, Run

```bash
# check it works
pre-commit run --all-files
pre-commit install
```

Run every so often to update the pre-commit hooks

```bash
pre-commit autoupdate
```

### Fixing Python formatting issues

```bash
ruff format tavern/ tests/
ruff --fix tavern/ tests/
```

### Fix yaml formatting issues

```bash
pre-commit run --all-files
```

## Creating a new release

1. Setup `~/.pypirc` according to the [official instructions](https://packaging.python.org/en/latest/specifications/pypirc/) 

1. Tag and push to git with `tbump <new-tag> --tag-message "<tag-message>"`

1. Upload to pypi with `flit publish`

## Building the documentation

Run this standalone for now: https://github.com/jupyter-book/mystmd/issues/2082

```bash
uv tool run --from mystmd myst build --html
```

### Watching for changes

To automatically rebuild when files in the `docs/` folder change:

```bash
uv tool run watchfiles "uv tool run --from mystmd myst build --html" --filter all docs myst.yml
```
