import dataclasses

import pytest

from tavern._core import exceptions
from tavern._core.starlark.expressions import eval_expression, eval_stage_expression


class TestEvalExpression:
    def test_simple_true(self):
        assert eval_expression("1 < 2", {}, description="test") is True

    def test_simple_false(self):
        assert eval_expression("1 > 2", {}, description="test") is False

    def test_variable_bound_directly(self):
        """Variables are bound as real values, not format-string interpolated"""
        assert eval_expression("var_x > 2", {"var_x": 3}, description="test") is True
        assert eval_expression("var_x > 2", {"var_x": 1}, description="test") is False

    def test_string_variable(self):
        assert (
            eval_expression(
                "some_var == 'value'", {"some_var": "value"}, description="test"
            )
            is True
        )

    def test_nested_variable(self):
        assert (
            eval_expression(
                "thing['a']['b'] == 1",
                {"thing": {"a": {"b": 1}}},
                description="test",
            )
            is True
        )

    def test_format_syntax_is_not_supported(self):
        """'{var}' style formatting is deliberately not done - the string is just a
        literal string, so this quietly compares '{some_var}' to 'value'"""
        assert (
            eval_expression(
                "'{some_var}' == 'value'", {"some_var": "value"}, description="test"
            )
            is False
        )

    def test_undefined_variable(self):
        with pytest.raises(exceptions.EvalError) as exc_info:
            eval_expression("not_a_variable", {}, description="test")

        assert "not_a_variable" in str(exc_info.value)

    def test_invalid_syntax(self):
        with pytest.raises(exceptions.EvalError):
            eval_expression("hello i am a test <<<", {}, description="test")

    def test_non_bool_result(self):
        with pytest.raises(exceptions.EvalError) as exc_info:
            eval_expression("'a string'", {}, description="test")

        assert "did not evaluate to True/False" in str(exc_info.value)

    def test_non_identifier_variables_are_ignored(self):
        """Variables which can't be used as starlark names shouldn't break everything"""
        variables = {"with-a-dash": 1, "1_starts_with_number": 2, "fine": 3}

        assert eval_expression("fine == 3", variables, description="test") is True

    def test_reserved_word_variables_are_ignored(self):
        assert (
            eval_expression("fine == 3", {"load": 1, "fine": 3}, description="test")
            is True
        )

    def test_opaque_variables_can_be_bound(self):
        """Objects which can't be represented in starlark shouldn't break binding"""

        class Something:
            pass

        variables = {"opaque": Something(), "fine": 3}

        assert eval_expression("fine == 3", variables, description="test") is True

    def test_response_struct_attribute_access(self):
        response = {"status_code": 200, "body": {"status": "ready"}, "failed": False}

        assert (
            eval_expression(
                "response.status_code == 200 and response.body['status'] == 'ready'",
                {},
                response=response,
                description="test",
            )
            is True
        )

    def test_response_and_variables_together(self):
        response = {"status_code": 500}

        assert (
            eval_expression(
                "response.status_code == expected_code",
                {"expected_code": 500},
                response=response,
                description="test",
            )
            is True
        )

    def test_response_missing_key(self):
        with pytest.raises(exceptions.EvalError):
            eval_expression(
                "response.nonexistent == 1",
                {},
                response={"status_code": 200},
                description="test",
            )


class TestStageExpressionGuard:
    def test_requires_experimental_flag(self, fix_test_config):
        config = dataclasses.replace(
            fix_test_config, experimental_starlark_pipeline=False
        )

        with pytest.raises(exceptions.UnexpectedKeysError) as exc_info:
            eval_stage_expression("if", "1 < 2", {"name": "a stage"}, config)

        assert "--tavern-experimental-starlark-pipeline" in str(exc_info.value)

    def test_works_with_experimental_flag(self, fix_test_config):
        assert (
            eval_stage_expression("if", "1 < 2", {"name": "a stage"}, fix_test_config)
            is True
        )

    def test_stage_name_in_error(self, fix_test_config):
        with pytest.raises(exceptions.EvalError) as exc_info:
            eval_stage_expression(
                "if", "not_a_variable", {"name": "a stage"}, fix_test_config
            )

        assert "a stage" in str(exc_info.value)
