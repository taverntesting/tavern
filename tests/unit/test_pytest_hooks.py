import os
import pathlib
from dataclasses import dataclass
from unittest.mock import Mock, patch

import pytest
from faker import Faker

from tavern._core import exceptions
from tavern._core.pytest.file import YamlFile, _get_parametrized_items


@dataclass
class MockArgs:
    session: pytest.Session
    parent: pytest.File
    path: pathlib.Path


def mock_args():
    """Get a basic test config to initialise a YamlFile object with"""

    path = pathlib.Path("abc")

    cargs = {"rootdir": "abc", "path": path}

    config = Mock(**cargs, rootpath="abc")

    session = Mock(_initialpaths=[], config=config)

    parent = Mock(
        spec=os.PathLike,
        config=config,
        parent=None,
        nodeid="sdlfs",
        **cargs,
        session=session,
    )

    return MockArgs(session, parent, path)


def get_basic_parametrize_mark(faker):
    """Get a random 'normal' parametrize mark"""
    return {"parametrize": {"key": faker.name(), "vals": [faker.name(), 2, 3]}}


def get_joined_parametrize_mark(faker):
    """Get a random 'combined' parametrize mark"""
    return {
        "parametrize": {
            "key": [faker.name(), faker.name()],
            "vals": [["w", "x"], ["y", "z"]],
        }
    }


def get_parametrised_tests(marks):
    args = mock_args()
    y = YamlFile.from_parent(args.parent, path=args.path)
    y.session = args.session

    spec = {"test_name": "a test", "stages": []}

    gen = _get_parametrized_items(y, spec, marks, [])

    return list(gen)


def test_none():
    marks = []

    tests = get_parametrised_tests(marks)

    # Only 1
    assert len(tests) == 1


@pytest.mark.parametrize("faker", [Faker(), Faker("zh_CN")])
class TestMakeFile:
    def test_only_single(self, faker):
        marks = [get_basic_parametrize_mark(faker)]

        tests = get_parametrised_tests(marks)

        # [1]
        # [2]
        # [3]
        assert len(tests) == 3

    def test_only_basic(self, faker):
        marks = [
            get_basic_parametrize_mark(faker),
            get_basic_parametrize_mark(faker),
            get_basic_parametrize_mark(faker),
        ]
        tests = get_parametrised_tests(marks)

        # [1, 1, 1]
        # [1, 1, 2]
        # [1, 1, 3]
        # [1, 2, 1]
        # [1, 2, 2]
        # [1, 2, 3]
        # etc.
        assert len(tests) == 27

    def test_double(self, faker):
        marks = [get_joined_parametrize_mark(faker), get_basic_parametrize_mark(faker)]

        tests = get_parametrised_tests(marks)

        # [w, x, 1]
        # [w, x, 2]
        # [w, x, 3]
        # [y, z, 1]
        # [y, z, 2]
        # [y, z, 3]
        assert len(tests) == 6

    def test_double_double(self, faker):
        marks = [
            get_joined_parametrize_mark(faker),
            get_joined_parametrize_mark(faker),
            get_basic_parametrize_mark(faker),
        ]

        tests = get_parametrised_tests(marks)

        # [w, x, w, x, 1]
        # [w, x, w, x, 2]
        # [w, x, w, x, 3]
        # [w, x, y, z, 1]
        # [w, x, y, z, 2]
        # [w, x, y, z, 3]
        # etc.
        assert len(tests) == 12

    def test_double_double_single(self, faker):
        marks = [
            get_joined_parametrize_mark(faker),
            get_joined_parametrize_mark(faker),
            get_basic_parametrize_mark(faker),
            get_basic_parametrize_mark(faker),
        ]

        tests = get_parametrised_tests(marks)

        # [w, x, w, x, 1, 1]
        # [w, x, w, x, 1, 2]
        # [w, x, w, x, 2, 1]
        # [w, x, w, x, 2, 2]
        # [w, x, y, z, 1, 1]
        # [w, x, y, z, 1, 2]
        # etc.
        assert len(tests) == 36

    @pytest.mark.parametrize(
        ("keys", "values"),
        (
            ("a", ["b", "c", "d"]),
            (["a"], ["b", "c", "d"]),
            ("a", {"k": "v"}),
            (["a"], {"k": "v"}),
            (["a", "b"], [["b", "c"]]),
            (["a", "b"], [["b", "c"], [{"a": "b"}, {"a": "b"}]]),
            (["a", "b"], [["b", "c"], ["b", "c"], ["d", "e"]]),
        ),
    )
    def test_ext_function_top_level(self, faker, keys, values):
        with patch(
            "tavern._core.pytest.file.get_wrapped_create_function",
            lambda _: lambda: values,
        ):
            marks = [
                {"parametrize": {"key": keys, "vals": {"$ext": {"function": "a:v"}}}}
            ]

            tests = get_parametrised_tests(marks)

            assert len(tests) == len(values)

    @pytest.mark.parametrize(
        ("keys", "values"),
        (
            # must return a list of lists
            (["a", "b"], {"a": "b"}),
            # must return a list of lists
            (["a", "b"], [{"a": "b"}]),
            # must return a list of lists
            (["a", "b"], [{"a": "b"}, {"a": "b"}]),
            # must return a list of lists
            (["a", "b"], "b"),
            # must return a list of lists
            (["a", "b"], ["b", "c"]),
            # must return a list of lists, where each element is also 3 long
            (["a", "b"], [["b", "c", "e"]]),
            # must return a list of lists, where each element is also 3 long
            (["a", "b"], [["b"]]),
        ),
    )
    def test_ext_function_top_level_invalid(self, faker, keys, values):
        with patch(
            "tavern._core.pytest.file.get_wrapped_create_function",
            lambda _: lambda: values,
        ):
            marks = [
                {"parametrize": {"key": keys, "vals": {"$ext": {"function": "a:v"}}}}
            ]

            with pytest.raises(exceptions.BadSchemaError):
                get_parametrised_tests(marks)


def test_doc_string():
    args = mock_args()
    y = YamlFile.from_parent(args.parent, path=args.path)

    assert isinstance(y.obj.__doc__, str)
