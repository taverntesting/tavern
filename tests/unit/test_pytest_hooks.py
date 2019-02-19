import pytest
from faker import Faker
from mock import Mock

from tavern.testutils.pytesthook.file import YamlFile


def mock_args():
    """Get a basic test config to initialise a YamlFile object with"""

    fspath = "abc"

    cargs = {"rootdir": "abc", "fspath": fspath}

    config = Mock(**cargs)

    session = Mock(_initialpaths=[], config=config)

    parent = Mock(config=config, parent=None, nodeid="sdlfs", **cargs)

    return {"session": session, "parent": parent, "fspath": fspath}


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
    y = YamlFile(**mock_args())

    spec = {"test_name": "a test"}

    gen = y.get_parametrized_items(spec, marks, [])

    return list(gen)


def test_none():
    marks = []

    tests = get_parametrised_tests(marks)

    # Only 1
    assert len(tests) == 1


@pytest.mark.parametrize("faker", [Faker(), Faker("zh_CN")])
class TestMakeFile(object):
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
