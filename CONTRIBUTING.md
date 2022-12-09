# Contributing

## Updating/adding a dependency

1. Add or update the dependency in [pyproject.toml](/pyproject.toml)

1. Update requirements files (BOTH of them)

       pip-compile --all-extras --resolver=backtracking pyproject.toml --generate-hashes > requirements.txt
       pip-compile --all-extras --resolver=backtracking pyproject.toml --strip-extras > constraints.txt

1. Run tests

       ./scripts/smoke.bash
