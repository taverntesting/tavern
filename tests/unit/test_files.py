import contextlib
import dataclasses
import os
import pathlib
import tempfile
from collections.abc import Callable, Generator
from typing import Any
from unittest.mock import Mock

import pytest
import yaml

from tavern._core import exceptions
from tavern._core.files import _find_file_in_include_path, _get_include_dirs
from tavern._core.pytest.file import YamlFile
from tavern._core.pytest.item import YamlItem


@pytest.fixture(scope="function")
def tavern_test_content():
    """return some example tests"""

    test_docs = [
        {"test_name": "First test", "stages": [{"name": "stage 1"}]},
        {"test_name": "Second test", "stages": [{"name": "stage 2"}]},
        {"test_name": "Third test", "stages": [{"name": "stage 3"}]},
    ]

    return test_docs


@contextlib.contextmanager
def tavern_test_file(test_content: list[Any]) -> Generator[pathlib.Path, Any, None]:
    """Create a temporary YAML file with multiple documents"""

    with tempfile.TemporaryDirectory() as tmpdir:
        file_path = pathlib.Path(tmpdir) / "test.yaml"

        # Write the documents to the file
        with file_path.open("w", encoding="utf-8") as f:
            for doc in test_content:
                yaml.dump(doc, f)
                f.write("---\n")

        yield file_path


@dataclasses.dataclass
class Opener:
    """Simple mock for generating items because pytest makes it hard to wrap
    their internal functionality"""

    path: pathlib.Path
    _generate_items: Callable[[dict], Any]


class TestGenerateFiles:
    @pytest.mark.parametrize("with_merge_down_test", (True, False))
    def test_multiple_documents(self, tavern_test_content, with_merge_down_test):
        """Verify that multiple documents in a YAML file result in multiple tests"""

        # Collect all tests
        if with_merge_down_test:
            tavern_test_content.insert(0, {"includes": [], "is_defaults": True})

        def generate_yamlitem(test_spec):
            mock = Mock(spec=YamlItem)
            mock.name = test_spec["test_name"]
            yield mock

        with tavern_test_file(tavern_test_content) as filename:
            tests = list(
                YamlFile.collect(
                    Opener(
                        path=filename,
                        _generate_items=generate_yamlitem,
                    )
                )
            )

        assert len(tests) == 3

        # Verify each test has the correct name
        expected_names = ["First test", "Second test", "Third test"]
        for test, expected_name in zip(tests, expected_names):
            assert test.name == expected_name

    @pytest.mark.parametrize(
        "content, exception",
        (
            ({"kookdff": "?A?A??"}, exceptions.BadSchemaError),
            ({"test_name": "name", "stages": [{"name": "lflfl"}]}, TypeError),
        ),
    )
    def test_reraise_exception(
        self, tavern_test_content, content: dict, exception: BaseException
    ):
        """Verify that exceptions are properly reraised when loading YAML test files.

        Test that when an exception occurs during test generation, it is properly
        reraised as a schema error if the schema is bad."""

        def raise_error(test_spec):
            raise TypeError

        tavern_test_content.insert(0, content)

        with tavern_test_file(tavern_test_content) as filename:
            with pytest.raises(exception):
                list(
                    YamlFile.collect(
                        Opener(
                            path=filename,
                            _generate_items=raise_error,
                        )
                    )
                )


class TestGetIncludeDirs:
    def test_default_dirs_no_test_file(self, monkeypatch):
        monkeypatch.delenv("TAVERN_INCLUDE", raising=False)
        dirs = _get_include_dirs()
        assert dirs == [os.path.curdir]

    def test_test_file_directory_first(self, tmp_path, monkeypatch):
        monkeypatch.delenv("TAVERN_INCLUDE", raising=False)
        test_file = str(tmp_path / "test.tavern.yaml")
        dirs = _get_include_dirs(test_file)
        assert dirs[0] == str(tmp_path)

    def test_env_var_paths(self, tmp_path, monkeypatch):
        monkeypatch.delenv("TAVERN_INCLUDE", raising=False)
        include_dir = str(tmp_path / "includes")
        monkeypatch.setenv("TAVERN_INCLUDE", include_dir)
        dirs = _get_include_dirs()
        assert dirs == [os.path.curdir, include_dir]

    def test_multiple_env_paths(self, tmp_path, monkeypatch):
        monkeypatch.delenv("TAVERN_INCLUDE", raising=False)
        path1 = str(tmp_path / "inc1")
        path2 = str(tmp_path / "inc2")
        monkeypatch.setenv("TAVERN_INCLUDE", f"{path1}:{path2}")
        dirs = _get_include_dirs()
        assert dirs == [os.path.curdir, path1, path2]

    def test_env_var_expansion(self, tmp_path, monkeypatch):
        monkeypatch.delenv("TAVERN_INCLUDE", raising=False)
        include_dir = str(tmp_path / "includes")
        monkeypatch.setenv("SOME_DIR", include_dir)
        monkeypatch.setenv("TAVERN_INCLUDE", "$SOME_DIR")
        dirs = _get_include_dirs()
        assert dirs == [os.path.curdir, include_dir]


class TestFindFileInIncludePath:
    def test_absolute_path(self, tmp_path):
        f = tmp_path / "test.txt"
        f.write_text("hello")
        result = _find_file_in_include_path(str(f))
        assert result == str(f)

    def test_relative_from_test_file_dir(self, tmp_path, monkeypatch):
        monkeypatch.delenv("TAVERN_INCLUDE", raising=False)
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        test_file = str(test_dir / "test.tavern.yaml")
        f = test_dir / "data.txt"
        f.write_text("hello")
        result = _find_file_in_include_path("data.txt", test_file)
        assert result == str(f)

    def test_relative_from_cwd(self, tmp_path, monkeypatch):
        monkeypatch.delenv("TAVERN_INCLUDE", raising=False)
        f = tmp_path / "data.txt"
        f.write_text("hello")
        monkeypatch.chdir(tmp_path)
        result = _find_file_in_include_path("data.txt")
        assert result == str(f)

    def test_relative_from_env_var(self, tmp_path, monkeypatch):
        include_dir = tmp_path / "includes"
        include_dir.mkdir()
        f = include_dir / "data.txt"
        f.write_text("hello")
        monkeypatch.setenv("TAVERN_INCLUDE", str(include_dir))
        result = _find_file_in_include_path("data.txt")
        assert result == str(f)

    def test_not_found(self, monkeypatch, tmp_path):
        monkeypatch.delenv("TAVERN_INCLUDE", raising=False)
        monkeypatch.chdir(tmp_path)
        with pytest.raises(exceptions.BadSchemaError):
            _find_file_in_include_path("nonexistent.txt")

    def test_test_file_dir_priority(self, tmp_path, monkeypatch):
        monkeypatch.delenv("TAVERN_INCLUDE", raising=False)
        test_dir = tmp_path / "tests"
        test_dir.mkdir()
        test_file = str(test_dir / "test.tavern.yaml")

        # Create file in cwd
        cwd_file = tmp_path / "data.txt"
        cwd_file.write_text("cwd")
        # Create file in test dir
        test_file_data = test_dir / "data.txt"
        test_file_data.write_text("test")

        monkeypatch.chdir(tmp_path)
        result = _find_file_in_include_path("data.txt", test_file)
        assert result == str(test_file_data)
