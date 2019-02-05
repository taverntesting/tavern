import base64
import os

import pytest
from mock import Mock, patch

from tavern.testutils.pytesthook import YamlFile
from tavern.util import exceptions


def mock_args():
    """Get a basic test config to initialist a YamlFile object with"""

    fspath = "abc"

    cargs = {"rootdir": "abc", "fspath": fspath}

    config = Mock(**cargs)

    session = Mock(_initialpaths=[], config=config)

    parent = Mock(config=config, parent=None, nodeid="sdlfs", **cargs)

    return {"session": session, "parent": parent, "fspath": fspath}


def genkey():
    """Get a random short key name"""
    return base64.b64encode(os.urandom(5)).decode("utf8")


def get_basic_parametrize_mark():
    """Get a random 'normal' parametrize mark"""
    return {"parametrize": {"key": genkey(), "vals": [1, 2, 3]}}


def get_joined_parametrize_mark():
    """Get a random 'combined' parametrize mark"""
    return {
        "parametrize": {"key": [genkey(), genkey()], "vals": [["w", "x"], ["y", "z"]]}
    }


def get_parametrised_tests(marks):
    y = YamlFile(**mock_args())

    spec = {"test_name": "a test"}

    gen = y.get_parametrized_items(spec, marks, [])

    return list(gen)


class TestMakeFile(object):
    def test_only_single(self):
        marks = [ ]

        tests = get_parametrised_tests(marks)

        # Only 1
        assert len(tests) == 1

    def test_only_single(self):
        marks = [
            get_basic_parametrize_mark(),
            get_basic_parametrize_mark(),
            get_basic_parametrize_mark(),
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

    def test_double(self):
        marks = [get_joined_parametrize_mark(), get_basic_parametrize_mark()]

        tests = get_parametrised_tests(marks)

        # [w, x, 1]
        # [w, x, 2]
        # [w, x, 3]
        # [y, z, 1]
        # [y, z, 2]
        # [y, z, 3]
        assert len(tests) == 6

    def test_double_double(self):
        marks = [
            get_joined_parametrize_mark(),
            get_joined_parametrize_mark(),
            get_basic_parametrize_mark(),
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

    def test_double_double_single(self):
        marks = [
            get_joined_parametrize_mark(),
            get_joined_parametrize_mark(),
            get_basic_parametrize_mark(),
            get_basic_parametrize_mark(),
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
