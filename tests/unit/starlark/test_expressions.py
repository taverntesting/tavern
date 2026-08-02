import dataclasses

import pytest

from tavern._core import exceptions
from tavern._core.starlark.expressions import eval_expression, eval_stage_expression


class TestEvalExpression:
    def test_simple_true(self):
        assert eval_expression("1 < 2", {}, description="test") is True

    def test_simple_false(self):
        assert eval_expression("1 > 2", {}, description="test") is False

    def test_variable_interpolated(self):
        """Variables are interpolated into the expression before it is evaluated"""
        assert eval_expression("{var_x} > 2", {"var_x": 3}, description="test") is True
        assert eval_expression("{var_x} > 2", {"var_x": 1}, description="test") is False

    def test_string_variable(self):
        assert (
            eval_expression(
                "'{some_var}' == 'value'", {"some_var": "value"}, description="test"
            )
            is True
        )

    def test_nested_variable(self):
        assert (
            eval_expression(
                "{thing.a.b} == 1",
                {"thing": {"a": {"b": 1}}},
                description="test",
            )
            is True
        )

    def test_variable_with_a_dash(self):
        """Names which aren't valid starlark identifiers work fine when interpolated"""
        assert (
            eval_expression("{with-a-dash} > 4", {"with-a-dash": 5}, description="test")
            is True
        )

    def test_format_spec(self):
        assert (
            eval_expression(
                "'{my_float:.2f}' == '1.50'", {"my_float": 1.5}, description="test"
            )
            is True
        )

    def test_undefined_variable(self):
        with pytest.raises(exceptions.EvalError) as exc_info:
            eval_expression("{not_a_variable} > 1", {}, description="test")

        assert "not_a_variable" in str(exc_info.value)

    def test_undefined_bare_name(self):
        """A bare name which isn't interpolated is just undefined in starlark"""
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

    def test_reserved_word_variables(self):
        """Names which are reserved words in starlark are fine when interpolated"""
        assert (
            eval_expression("{load} == 1", {"load": 1, "fine": 3}, description="test")
            is True
        )

    def test_unreferenced_variables_are_ignored(self):
        """Variables which aren't referenced shouldn't break anything, whatever they are"""

        class Something:
            pass

        variables = {
            "opaque": Something(),
            "1_starts_with_number": 2,
            "fine": 3,
        }

        assert eval_expression("{fine} == 3", variables, description="test") is True

    def test_literal_braces_must_be_escaped(self):
        assert eval_expression("{{'a': 1}}['a'] == 1", {}, description="test") is True

    def test_multiline_script(self):
        """An expression can be a whole script - the last statement is the result"""
        expr = """
n_big = len([i for i in {numbers} if i > 2])
n_big == 2
"""

        assert (
            eval_expression(expr, {"numbers": [1, 2, 3, 4]}, description="test") is True
        )

    def test_multiline_script_using_regex(self):
        """The 're' helper module is available, as in a control_flow script"""
        expr = """
match = re.search("v(\\\\d+)\\\\.(\\\\d+)", "{version}")
match != None and all([int(g) > 0 for g in match.groups])
"""

        assert eval_expression(expr, {"version": "v2.5"}, description="test") is True
        assert eval_expression(expr, {"version": "v0.5"}, description="test") is False

    def test_regex_which_does_not_match(self):
        expr = 're.search("v(\\\\d+)", "{version}") != None'

        assert eval_expression(expr, {"version": "banana"}, description="test") is False

    def test_run_stage_is_not_available(self):
        with pytest.raises(exceptions.EvalError) as exc_info:
            eval_expression('run_stage("a_stage").failed', {}, description="test")

        assert "only available in a 'control_flow' script" in str(exc_info.value)

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
                "response.status_code == {expected_code}",
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
