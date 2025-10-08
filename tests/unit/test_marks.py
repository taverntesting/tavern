import ast

import pytest

from tavern._core import exceptions
from tavern._core.pytest.file import _ast_node_to_literal, _format_test_marks


@pytest.mark.parametrize(
    "marks,expected",
    [
        (["skip"], ([pytest.mark.skip], [])),
        (["xfail"], ([pytest.mark.xfail], [])),
        (["slow"], ([pytest.mark.slow], [])),
        (["skip", "xfail"], ([pytest.mark.skip, pytest.mark.xfail], [])),
        (["xdist_group('group1')"], ([pytest.mark.xdist_group("group1")], [])),
        (
            ["xdist_group(group='group1')"],
            ([pytest.mark.xdist_group(group="group1")], []),
        ),
        (
            ["xdist_group('group1', 'group2')"],
            ([pytest.mark.xdist_group("group1", "group2")], []),
        ),
        (
            ["xdist_group(('group1', 'group2'),)"],
            (
                [
                    pytest.mark.xdist_group(
                        ("group1", "group2"),
                    )
                ],
                [],
            ),
        ),
        (
            ["skip", "xfail", 'xdist_group("group1")'],
            (
                [
                    pytest.mark.skip,
                    pytest.mark.xfail,
                    pytest.mark.xdist_group("group1"),
                ],
                [],
            ),
        ),
        # Additional test cases
        (["usefixtures('fixture1')"], ([pytest.mark.usefixtures("fixture1")], [])),
        (
            ["usefixtures('fixture1', 'fixture2')"],
            ([pytest.mark.usefixtures("fixture1", "fixture2")], []),
        ),
        (
            ["skipif(True, reason='test')"],
            ([pytest.mark.skipif(True, reason="test")], []),
        ),
        (
            ["xfail(reason='flaky')"],
            ([pytest.mark.xfail(reason="flaky")], []),
        ),
        (
            ["parametrize('a,b', [(1,2), (3,4)])"],
            ([pytest.mark.parametrize("a,b", [(1, 2), (3, 4)])], []),
        ),
        (
            ["skip", "slow", 'usefixtures("db")'],
            (
                [
                    pytest.mark.skip,
                    pytest.mark.slow,
                    pytest.mark.usefixtures("db"),
                ],
                [],
            ),
        ),
    ],
)
def test_format_test_marks(marks, expected):
    # Dummy values for fmt_vars and test_name, as required by the function signature
    result = _format_test_marks(marks, fmt_vars={}, test_name="dummy")
    assert result == expected


@pytest.mark.parametrize(
    "invalid_marks",
    [
        ["invalid(mark)"],  # nonexistent mark name
        ["xdist_group('unclosed)"],  # Invalid string literal
        ["xdist_group(missing_quote)"],  # Invalid arg format
    ],
)
def test_failing_format_marks(invalid_marks):
    with pytest.raises(exceptions.BadSchemaError):
        _format_test_marks(invalid_marks, fmt_vars={}, test_name="dummy")


class TestAstNodeToLiteral:
    """Tests for _ast_node_to_literal function"""

    def test_constant_node(self):
        """Test converting ast.Constant nodes"""

        # Test string constant
        node = ast.Constant(value="test_string")
        result = _ast_node_to_literal(node)
        assert result == "test_string"

        # Test numeric constant
        node = ast.Constant(value=42)
        result = _ast_node_to_literal(node)
        assert result == 42

        # Test boolean constant
        node = ast.Constant(value=True)
        result = _ast_node_to_literal(node)
        assert result is True

        # Test None constant
        node = ast.Constant(value=None)
        result = _ast_node_to_literal(node)
        assert result is None

    def test_list_node(self):
        """Test converting ast.List nodes"""

        # Empty list
        node = ast.List(elts=[], ctx=ast.Load())
        result = _ast_node_to_literal(node)
        assert result == []

        # List with constants
        node = ast.List(
            elts=[
                ast.Constant(value="a"),
                ast.Constant(value=1),
                ast.Constant(value=True),
            ],
            ctx=ast.Load(),
        )
        result = _ast_node_to_literal(node)
        assert result == ["a", 1, True]

        # Nested list
        inner_list = ast.List(elts=[ast.Constant(value="nested")], ctx=ast.Load())
        node = ast.List(
            elts=[ast.Constant(value="outer"), inner_list],
            ctx=ast.Load(),
        )
        result = _ast_node_to_literal(node)
        assert result == ["outer", ["nested"]]

    def test_dict_node(self):
        """Test converting ast.Dict nodes"""

        # Empty dict
        node = ast.Dict(keys=[], values=[], ctx=ast.Load())
        result = _ast_node_to_literal(node)
        assert result == {}

        # Dict with constants
        node = ast.Dict(
            keys=[
                ast.Constant(value="key1"),
                ast.Constant(value="key2"),
            ],
            values=[
                ast.Constant(value="value1"),
                ast.Constant(value=2),
            ],
            ctx=ast.Load(),
        )
        result = _ast_node_to_literal(node)
        assert result == {"key1": "value1", "key2": 2}

        # Nested dict
        inner_dict = ast.Dict(
            keys=[ast.Constant(value="inner_key")],
            values=[ast.Constant(value="inner_value")],
            ctx=ast.Load(),
        )
        node = ast.Dict(
            keys=[
                ast.Constant(value="outer_key"),
                ast.Constant(value="nested_dict"),
            ],
            values=[
                ast.Constant(value="outer_value"),
                inner_dict,
            ],
            ctx=ast.Load(),
        )
        result = _ast_node_to_literal(node)
        assert result == {
            "outer_key": "outer_value",
            "nested_dict": {"inner_key": "inner_value"},
        }

    def test_tuple_node(self):
        """Test converting ast.Tuple nodes"""

        # Empty tuple
        node = ast.Tuple(elts=[], ctx=ast.Load())
        result = _ast_node_to_literal(node)
        assert result == ()

        # Tuple with constants
        node = ast.Tuple(
            elts=[
                ast.Constant(value="a"),
                ast.Constant(value=1),
                ast.Constant(value=True),
            ],
            ctx=ast.Load(),
        )
        result = _ast_node_to_literal(node)
        assert result == ("a", 1, True)

        # Nested tuple
        inner_tuple = ast.Tuple(elts=[ast.Constant(value="nested")], ctx=ast.Load())
        node = ast.Tuple(
            elts=[ast.Constant(value="outer"), inner_tuple],
            ctx=ast.Load(),
        )
        result = _ast_node_to_literal(node)
        assert result == ("outer", ("nested",))

    def test_name_node_constants(self):
        """Test converting ast.Name nodes for constants"""

        # Test True
        node = ast.Name(id="True", ctx=ast.Load())
        result = _ast_node_to_literal(node)
        assert result is True

        # Test False
        node = ast.Name(id="False", ctx=ast.Load())
        result = _ast_node_to_literal(node)
        assert result is False

        # Test None
        node = ast.Name(id="None", ctx=ast.Load())
        result = _ast_node_to_literal(node)
        assert result is None

    def test_name_node_variable_reference_error(self):
        """Test that ast.Name nodes for variables raise ValueError"""

        node = ast.Name(id="some_variable", ctx=ast.Load())
        with pytest.raises(
            ValueError, match="Unsupported variable reference: some_variable"
        ):
            _ast_node_to_literal(node)

    def test_unsupported_node_type_error(self):
        """Test that unsupported node types raise ValueError"""

        # Use ast.Expr as an example of an unsupported node type
        node = ast.Expr(value=ast.Constant(value="test"))
        with pytest.raises(
            ValueError, match="Unsupported AST node type: <class 'ast.Expr'>"
        ):
            _ast_node_to_literal(node)


def test_format_test_marks_with_fmt_vars():
    """Test that _format_test_marks correctly substitutes formatted variables in mark arguments"""

    marks = ["skipif('{condition}', reason='{reason}')"]
    fmt_vars = {"condition": "True", "reason": "test_skip"}
    expected = ([pytest.mark.skipif("True", reason="test_skip")], [])

    result = _format_test_marks(marks, fmt_vars=fmt_vars, test_name="dummy")
    assert result == expected
