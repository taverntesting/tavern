"""Test that control_flow requires experimental flag"""

import pathlib
from unittest.mock import Mock

import pytest

from tavern._core.exceptions import BadSchemaError
from tavern._core.pytest.config import TavernInternalConfig, TestConfig
from tavern._core.run import run_test
from tavern._core.strict_util import StrictLevel


def test_control_flow_requires_experimental_flag():
    """Test that control_flow raises an error when experimental flag is not enabled"""
    # Create a test spec with control_flow
    test_spec = {
        "test_name": "test_control_flow",
        "control_flow": "def main():\n    pass",
        "stages": [],
    }

    # Create a TestConfig with experimental_starlark_pipeline=False
    global_cfg = TestConfig(
        variables={},
        strict=StrictLevel.all_on(),
        follow_redirects=False,
        stages=[],
        experimental_starlark_pipeline=False,
        tavern_internal=TavernInternalConfig(
            pytest_hook_caller=Mock(),
            backends={},
        ),
    )

    # Should raise BadSchemaError when control_flow is used without the flag
    with pytest.raises(BadSchemaError) as exc_info:
        run_test(
            pathlib.Path("/fake/path.tavern.yaml"),
            test_spec,
            global_cfg,
        )

    assert "control_flow requires --tavern-experimental-starlark-pipeline flag" in str(
        exc_info.value
    )


def test_control_flow_works_with_experimental_flag():
    """Test that control_flow works when experimental flag is enabled"""
    # Create a test spec with control_flow
    test_spec = {
        "test_name": "test_control_flow",
        "control_flow": "def main():\n    pass",
        "stages": [],
    }

    # Create a TestConfig with experimental_starlark_pipeline=True
    global_cfg = TestConfig(
        variables={},
        strict=StrictLevel.all_on(),
        follow_redirects=False,
        stages=[],
        experimental_starlark_pipeline=True,
        tavern_internal=TavernInternalConfig(
            pytest_hook_caller=Mock(),
            backends={},
        ),
    )

    # Should not raise an error about the flag
    # It will fail with a different error (ImportError for starlark module)
    # but that's expected since we're not testing the actual starlark execution
    with pytest.raises(Exception) as exc_info:
        run_test(
            pathlib.Path("/fake/path.tavern.yaml"),
            test_spec,
            global_cfg,
        )

    # Should NOT be a BadSchemaError about the flag
    # It should be an ImportError or starlark-related error
    assert not isinstance(exc_info.value, BadSchemaError) or "experimental" not in str(
        exc_info.value
    )
