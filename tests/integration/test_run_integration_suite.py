"""Runs the test_*.tavern.yaml files in this directory against the Flask server
from server.py, started in a background thread — no docker compose needed.

Each yaml file runs in a pytest subprocess because tavern patches the yaml
parser globally when it runs (see https://github.com/taverntesting/tavern/issues/825,
and the same pattern in tests/unit/test_allure.py).

tox-integration.ini's generic/noextra envs instead run the yaml files directly
against the docker compose server (exercising the tavern-ci and tavern.core.run
entrypoints); in that mode this module is collect-ignored by conftest.py.
"""

from pathlib import Path

import pytest

pytest_plugins = ["pytester"]

INTEGRATION_DIR = Path(__file__).parent
GLOBAL_CFG = INTEGRATION_DIR / "global_cfg.yaml"
YAML_FILES = sorted(INTEGRATION_DIR.glob("test_*.tavern.yaml"))
assert YAML_FILES, f"no test_*.tavern.yaml files found in {INTEGRATION_DIR}"


@pytest.fixture(autouse=True)
def _subprocess_env(monkeypatch, integration_server):
    monkeypatch.setenv("TEST_HOST", integration_server)
    monkeypatch.setenv("SECOND_URL_PART", "again")
    # So `external_functions: ext_functions:...` resolves in the subprocess
    monkeypatch.setenv("PYTHONPATH", str(INTEGRATION_DIR))
    # Lift conftest.py's collection guard for the subprocess
    monkeypatch.setenv("TAVERN_INTEGRATION_ALLOW_COLLECT", "1")


@pytest.mark.parametrize("yaml_file", YAML_FILES, ids=lambda p: p.name)
def test_integration_yaml_file(pytester, yaml_file, monkeypatch):
    # Schema validation resolves file upload paths relative to cwd (see
    # extensions.py::validate_file_spec), so run from this directory — after the
    # pytester fixture has already chdir'd into its tmpdir
    monkeypatch.chdir(INTEGRATION_DIR)

    result = pytester.runpytest_subprocess(
        str(yaml_file),
        "--tavern-global-cfg",
        str(GLOBAL_CFG),
        "-m",
        "not do_not_run",
        # Plugin loading dominates the subprocess startup time, so disable
        # everything the yaml tests don't use (cov is kept for coverage)
        "-p",
        "no:hypothesispytest",
        "-p",
        "no:xdist",
        "-p",
        "no:xdist.looponfail",
        "-p",
        "no:allure_pytest",
        "-p",
        "no:asyncio",
        "-p",
        "no:anyio",
        "-p",
        "no:faker",
        "-p",
        "no:random_order",
    )

    # NO_TESTS_COLLECTED is legitimate for a file whose every test is
    # deselected by the marker filter; anything else nonzero is a real failure.
    assert result.ret in (
        pytest.ExitCode.OK,
        pytest.ExitCode.NO_TESTS_COLLECTED,
    ), "\n".join(result.outlines[-200:] + result.errlines[-200:])
