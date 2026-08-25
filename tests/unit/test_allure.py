import json

pytest_plugins = ["pytester"]

PARAMETRIZED_TEST = """
---
test_name: Parametrized test

marks:
  - parametrize:
      key: wallet_address
      vals:
        - aaaaaaaa
        - bbbbbbbb

stages:
  - name: Request to a port nothing is listening on
    request:
      url: "http://localhost:1/{wallet_address}"
      method: GET
    response:
      status_code: 200
"""


def test_parametrized_items_have_unique_allure_history_ids(pytester):
    """Each parametrized test should be a separate test case in the allure report

    See https://github.com/taverntesting/tavern/issues/1078
    """
    pytester.makefile(".tavern.yaml", test_param=PARAMETRIZED_TEST)
    allure_dir = pytester.path / "allure"

    # In a subprocess because running a tavern test patches the yaml parser globally
    # (see https://github.com/taverntesting/tavern/issues/825)
    result = pytester.runpytest_subprocess("--alluredir", str(allure_dir))
    result.assert_outcomes(failed=2)

    reported = [json.loads(f.read_text()) for f in allure_dir.glob("*-result.json")]
    assert len(reported) == 2
    assert len({r["historyId"] for r in reported}) == 2
    assert {(p["name"], p["value"]) for r in reported for p in r["parameters"]} == {
        ("wallet_address", "'aaaaaaaa'"),
        ("wallet_address", "'bbbbbbbb'"),
    }
