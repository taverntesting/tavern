import dataclasses
import logging
import unittest.mock
from collections.abc import Mapping
from unittest.mock import patch

import pytest

from tavern._core import exceptions
from tavern._core.pytest.config import TestConfig
from tavern._core.run import run_test


def _run_test(
    stage: Mapping, test_block_config: TestConfig, run_mock: unittest.mock.Mock
) -> bool:
    """runs the test and returns whether the stage was run or not"""

    full_test = {
        "test_name": "A test with a single stage",
        "stages": [stage],
    }

    run_test("test_file_name", full_test, test_block_config)

    return run_mock.called


class TestSkipStage:
    @pytest.fixture(autouse=True)
    def run_mock(self):
        with patch("tavern._core.run._TestRunner.run_stage") as run_mock:
            yield run_mock

    @pytest.fixture(scope="function")
    def stage(self):
        return {
            "name": "test stage",
            "request": {"url": "https://example.com", "method": "GET"},
            "response": {"status_code": 200},
        }

    @pytest.fixture
    def test_block_config(self, includes):
        return dataclasses.replace(includes, variables={"env_vars": {}})

    def test_skip_true(self, stage, test_block_config, run_mock):
        """Skip stage when 'skip' is True"""

        stage["skip"] = True
        assert _run_test(stage, test_block_config, run_mock) is False

    def test_skip_false(self, stage, test_block_config, run_mock):
        """Don't skip stage when 'skip' is False"""

        stage["skip"] = False
        assert _run_test(stage, test_block_config, run_mock) is True

    def test_skip_simpleeval_true(self, stage, test_block_config, run_mock):
        """Skip stage when simpleeval expression evaluates to True"""

        stage["skip"] = "True"
        assert _run_test(stage, test_block_config, run_mock) is False

    def test_skip_simpleeval_false(self, stage, test_block_config, run_mock):
        """Don't skip stage when simpleeval expression evaluates to False"""

        stage["skip"] = "False"
        assert _run_test(stage, test_block_config, run_mock) is True

    def test_skip_env_var_true(self, stage, test_block_config, run_mock):
        """Skip stage when using a variable that evaluates to True"""

        stage["skip"] = "'{some_var}' == 'value'"
        test_block_config.variables.update({"some_var": "value"})

        assert _run_test(stage, test_block_config, run_mock) is False

    def test_skip_env_var_false(self, stage, test_block_config, run_mock):
        """Don't skip stage when using a variable that evaluates to False"""

        stage["skip"] = "'{some_var}' == 'value'"
        test_block_config.variables.update({"some_var": "value"})

        assert _run_test(stage, test_block_config, run_mock) is False

    def test_skip_invalid_var_types(self, stage, test_block_config, run_mock):
        """Error when cel types are wrong"""

        stage["skip"] = "'{some_var}' > 3"
        test_block_config.variables.update({"some_var": "value"})

        with pytest.raises(exceptions.EvalError):
            _run_test(stage, test_block_config, run_mock)

    @pytest.mark.xfail(
        reason="'KeyError: <_pytest.stash.StashKey object at 0x7fa6ac4852c0' ?????"
    )
    def test_skip_invalid_simpleeval(self, stage, test_block_config, caplog, run_mock):
        """Handle invalid simpleeval expressions gracefully"""

        stage["skip"] = "hello i am a test <<<"

        with caplog.at_level(logging.WARNING):
            _run_test(stage, test_block_config, run_mock)

        assert "unable to parse as simpleeval" in caplog.text

    def test_error_valid_simpleeval_missing_var(
        self, stage, test_block_config, run_mock
    ):
        """Handle missing variable"""

        stage["skip"] = "invalid_cel_expression"

        with pytest.raises(exceptions.EvalError):
            _run_test(stage, test_block_config, run_mock)

    def test_skip_non_bool_result(self, stage, test_block_config, run_mock):
        """Raise error when CEL returns non-boolean value"""

        stage["skip"] = "'not a boolean'"
        with pytest.raises(exceptions.EvalError):
            _run_test(stage, test_block_config, run_mock)

    def test_skip_empty_string(self, stage, test_block_config, run_mock):
        """Treat empty string as False"""

        stage["skip"] = ""
        assert _run_test(stage, test_block_config, run_mock) is True
