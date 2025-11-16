import contextlib
import dataclasses
import pathlib
import tempfile
from collections.abc import Callable, Generator
from typing import Any
from unittest.mock import Mock

import pytest
import yaml

from tavern._core import exceptions
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
