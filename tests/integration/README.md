# Random integration tests

Though there are full examples for testing MQTT, cookies, etc, this subfolder
contains more 'generic' tests such as testing regex functionality and pattern
matching that don't nicely slot into the examples. Essentially, tests in this
folder will typically consist of one stage (unless multi-stage functionality is
being tested), and will not require logging in.

All the tests run against the flask app in `server.py`, in one of two modes:

- **Plain `pytest`** (the default, also part of the top-level test run): the
  server is started in a background thread on a random port (one per
  pytest-xdist worker, if used) and each `test_*.tavern.yaml` file is run in a
  pytest subprocess via the `pytester` plugin — see
  `test_run_integration_suite.py`. No docker required.
- **`tox -c tox-integration.ini -e py3-generic`** (or `py3-noextra`): the server
  runs under docker compose and the yaml files are collected directly, which
  also exercises the `tavern-ci` CLI and `tavern.core.run` library entrypoints.
  This mode sets `TAVERN_INTEGRATION_ALLOW_COLLECT=1` (see `conftest.py`) to
  collect the yaml files in-process instead of via the pytester runner.
