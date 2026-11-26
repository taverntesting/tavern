"""Tests for '$ext' functions in request blocks, see update_from_ext"""

import sys
import types

import pytest

from tavern._core import exceptions
from tavern._core.dict_util import format_keys
from tavern._core.extfunctions import update_from_ext
from tavern._core.loader import ForceIncludeToken

MODULE_NAME = "unit_ext_functions"


@pytest.fixture(name="calls")
def fix_ext_module(monkeypatch):
    """Module of functions for '$ext' to use, returning the names of the ones called"""
    calls: list[str] = []
    module = types.ModuleType(MODULE_NAME)

    def register(name, returned):
        def func():
            calls.append(name)
            return returned

        setattr(module, name, func)

    register("building", {"building": "01"})
    register("floors", {"floors": {"count": 3}})
    register("numbers", [1, 2])
    register("text", "http://example.com")
    register("with_ext_key", {"items": [{"$ext": "literal"}]})

    def echo_kwargs(**kwargs):
        calls.append("echo_kwargs")
        return kwargs

    module.echo_kwargs = echo_kwargs  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, MODULE_NAME, module)

    return calls


def ext(name, **extra):
    return {"function": f"{MODULE_NAME}:{name}", **extra}


class TestTopLevelExt:
    def test_mapping_result_merged_into_block(self, calls):
        request_args = {"json": {"goodbye": "now", "$ext": ext("building")}}

        update_from_ext(request_args, ["json"])

        assert request_args["json"] == {"goodbye": "now", "building": "01"}
        assert calls == ["building"]

    def test_non_mapping_result_replaces_block(self, calls):
        request_args = {"url": {"$ext": ext("text")}}

        update_from_ext(request_args, ["url"])

        assert request_args["url"] == "http://example.com"
        assert calls == ["text"]

    def test_missing_block_is_ignored(self, calls):
        request_args = {"data": "text"}

        update_from_ext(request_args, ["json", "data"])

        assert request_args == {"data": "text"}
        assert not calls

    def test_blocks_without_ext_are_unchanged(self, calls):
        request_args = {
            "json": {"$extx": 1, "items": [{"nested": ext("building")}]},
            "params": {"like": "$ext"},
            "timeout": (1, 2),
        }

        update_from_ext(request_args, ["json", "params", "timeout"])

        assert request_args == {
            "json": {"$extx": 1, "items": [{"nested": ext("building")}]},
            "params": {"like": "$ext"},
            "timeout": (1, 2),
        }
        assert not calls


class TestNestedExt:
    def test_merged_into_list_item(self, calls):
        """The example from https://github.com/taverntesting/tavern/issues/563"""
        request_args = {
            "json": [{"some_id": 123, "gender": "Female", "$ext": ext("building")}]
        }

        update_from_ext(request_args, ["json"])

        assert request_args["json"] == [
            {"some_id": 123, "gender": "Female", "building": "01"}
        ]
        assert calls == ["building"]

    def test_merged_into_nested_dict(self, calls):
        request_args = {
            "json": {"outer": {"inner": {"a": 1, "$ext": ext("building")}}, "b": 2}
        }

        update_from_ext(request_args, ["json"])

        assert request_args["json"] == {
            "outer": {"inner": {"a": 1, "building": "01"}},
            "b": 2,
        }

    def test_mapping_result_is_merged_deeply(self, calls):
        request_args = {
            "json": {"house": {"floors": {"height": 2}, "$ext": ext("floors")}}
        }

        update_from_ext(request_args, ["json"])

        assert request_args["json"] == {
            "house": {"floors": {"height": 2, "count": 3}},
        }

    def test_non_mapping_result_replaces_dict(self, calls):
        request_args = {"json": {"values": {"$ext": ext("numbers")}, "b": 2}}

        update_from_ext(request_args, ["json"])

        assert request_args["json"] == {"values": [1, 2], "b": 2}

    def test_inside_tuple(self, calls):
        request_args = {"json": {"pair": ({"a": 1}, {"$ext": ext("text")})}}

        update_from_ext(request_args, ["json"])

        assert request_args["json"] == {"pair": ({"a": 1}, "http://example.com")}

    def test_top_level_and_nested_together(self, calls):
        request_args = {
            "json": {
                "$ext": ext("building"),
                "items": [{"$ext": ext("numbers")}, {"$ext": ext("floors")}],
            }
        }

        update_from_ext(request_args, ["json"])

        assert request_args["json"] == {
            "building": "01",
            "items": [[1, 2], {"floors": {"count": 3}}],
        }
        assert calls == ["building", "numbers", "floors"]

    def test_nothing_else_is_called_when_block_is_replaced(self, calls):
        request_args = {
            "json": {"$ext": ext("numbers"), "items": [{"$ext": ext("building")}]}
        }

        update_from_ext(request_args, ["json"])

        assert request_args["json"] == [1, 2]
        assert calls == ["numbers"]

    def test_ext_arguments_are_not_searched(self, calls):
        kwargs = {"payload": {"$ext": "literal"}}
        request_args = {
            "json": {"a": {"$ext": ext("echo_kwargs", extra_kwargs=kwargs)}}
        }

        update_from_ext(request_args, ["json"])

        assert request_args["json"] == {"a": {"payload": {"$ext": "literal"}}}
        assert calls == ["echo_kwargs"]

    def test_returned_value_is_not_searched(self, calls):
        request_args = {"json": {"a": {"$ext": ext("with_ext_key")}}}

        update_from_ext(request_args, ["json"])

        assert request_args["json"] == {"a": {"items": [{"$ext": "literal"}]}}
        assert calls == ["with_ext_key"]

    def test_included_variables_are_not_searched(self, calls):
        """Data from !force_format_include is sent as it is"""
        saved = {"$ext": ext("building"), "items": [{"$ext": ext("numbers")}]}
        request_args = format_keys(
            {
                "json": {
                    "direct": ForceIncludeToken("{saved}"),
                    "in_list": [ForceIncludeToken("{saved}")],
                }
            },
            {"saved": saved},
        )

        update_from_ext(request_args, ["json"])

        assert request_args["json"] == {"direct": saved, "in_list": [saved]}
        assert not calls

    @pytest.mark.parametrize(
        "block, expected",
        (
            (None, exceptions.InvalidExtFunctionError),
            ("a string", exceptions.InvalidExtFunctionError),
            ({"extra_kwargs": {}}, exceptions.BadSchemaError),
        ),
    )
    def test_invalid_block_raises(self, calls, block, expected):
        request_args = {"json": {"items": [{"$ext": block}]}}

        with pytest.raises(expected):
            update_from_ext(request_args, ["json"])
