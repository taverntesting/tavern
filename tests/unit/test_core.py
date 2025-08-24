import ast
import copy
import dataclasses
import json
import os
import uuid
from copy import deepcopy
from unittest.mock import MagicMock, Mock, patch

import paho.mqtt.client as paho
import pytest
import requests

from tavern._core import exceptions
from tavern._core.pytest.file import _ast_node_to_literal
from tavern._core.pytest.util import load_global_cfg
from tavern._core.run import run_test
from tavern._plugins.mqtt.client import MQTTClient


@pytest.fixture(name="fulltest")
def fix_example_test():
    spec = {
        "test_name": "A test with a single stage",
        "stages": [
            {
                "name": "step 1",
                "request": {"url": "http://www.google.com", "method": "GET"},
                "response": {
                    "status_code": 200,
                    "json": {"key": "value"},
                    "headers": {"content-type": "application/json"},
                },
            }
        ],
    }

    return spec


@pytest.fixture(name="mockargs")
def fix_mock_response_args(fulltest):
    response = copy.deepcopy(fulltest["stages"][0]["response"])
    content = response["json"]

    args = {
        "spec": requests.Response,
        "content": json.dumps(content).encode("utf8"),
        "status_code": response["status_code"],
        "json": lambda: content,
        "headers": response["headers"],
    }

    return args


class TestRunStages:
    def test_success(self, fulltest, mockargs, includes):
        """Successful test"""

        mock_response = Mock(**mockargs)

        with patch(
            "tavern._plugins.rest.request.requests.Session.request",
            return_value=mock_response,
        ) as pmock:
            run_test("heif", fulltest, includes)

        assert pmock.called

    def test_invalid_code(self, fulltest, mockargs, includes):
        """Wrong status code"""

        mockargs["status_code"] = 400

        mock_response = Mock(**mockargs)

        with patch(
            "tavern._plugins.rest.request.requests.Session.request",
            return_value=mock_response,
        ) as pmock:
            with pytest.raises(exceptions.TestFailError):
                run_test("heif", fulltest, includes)

        assert pmock.called

    def test_invalid_body(self, fulltest, mockargs, includes):
        """Wrong body returned"""

        mockargs["json"] = lambda: {"wrong": "thing"}

        mock_response = Mock(**mockargs)

        with patch(
            "tavern._plugins.rest.request.requests.Session.request",
            return_value=mock_response,
        ) as pmock:
            with pytest.raises(exceptions.TestFailError):
                run_test("heif", fulltest, includes)

        assert pmock.called

    def test_invalid_headers(self, fulltest, mockargs, includes):
        """Wrong headers"""

        mockargs["headers"] = {"content-type": "application/x-www-url-formencoded"}

        mock_response = Mock(**mockargs)

        with patch(
            "tavern._plugins.rest.request.requests.Session.request",
            return_value=mock_response,
        ) as pmock:
            with pytest.raises(exceptions.TestFailError):
                run_test("heif", fulltest, includes)

        assert pmock.called


class TestIncludeStages:
    @pytest.fixture
    def fake_stages(self):
        stages = [
            {
                "id": "my_external_stage",
                "name": "My external stage",
                "request": {"url": "http://www.bing.com", "method": "GET"},
                "response": {
                    "status_code": 200,
                    "json": {"key": "value"},
                    "headers": {"content-type": "application/json"},
                },
            }
        ]

        return stages

    def check_mocks_called(self, pmock):
        assert pmock.called

        # We expect 2 calls, first to bing (external stage),
        # then google (part of fulltest)
        assert len(pmock.call_args_list) == 2
        args, kwargs = pmock.call_args_list[0]
        assert kwargs["url"] == "http://www.bing.com"
        args, kwargs = pmock.call_args_list[1]
        assert kwargs["url"] == "http://www.google.com"

    def test_included_stage(self, fulltest, mockargs, includes, fake_stages):
        """Load stage from includes"""
        mock_response = Mock(**mockargs)

        stage_includes = [{"stages": fake_stages}]

        newtest = deepcopy(fulltest)
        newtest["includes"] = stage_includes
        newtest["stages"].insert(0, {"type": "ref", "id": "my_external_stage"})

        with patch(
            "tavern._plugins.rest.request.requests.Session.request",
            return_value=mock_response,
        ) as pmock:
            run_test("heif", newtest, includes)

        self.check_mocks_called(pmock)

    def test_included_finally_stage(self, fulltest, mockargs, includes, fake_stages):
        """Load stage from includes"""
        mock_response = Mock(**mockargs)

        stage_includes = [{"stages": fake_stages}]

        newtest = deepcopy(fulltest)
        newtest["includes"] = stage_includes
        newtest["finally"] = [{"type": "ref", "id": "my_external_stage"}]

        with patch(
            "tavern._plugins.rest.request.requests.Session.request",
            return_value=mock_response,
        ) as pmock:
            run_test("bloo", newtest, includes)

        pmock.call_args_list = list(reversed(pmock.call_args_list))
        self.check_mocks_called(pmock)

    def test_global_stage(self, fulltest, mockargs, includes, fake_stages):
        """Load stage from global config"""
        mock_response = Mock(**mockargs)

        stage_includes = []

        newtest = deepcopy(fulltest)
        newtest["includes"] = stage_includes
        newtest["stages"].insert(0, {"type": "ref", "id": "my_external_stage"})

        includes = dataclasses.replace(includes, stages=fake_stages)

        with patch(
            "tavern._plugins.rest.request.requests.Session.request",
            return_value=mock_response,
        ) as pmock:
            run_test("heif", newtest, includes)

        self.check_mocks_called(pmock)

    def test_both_stages(self, fulltest, mockargs, includes, fake_stages):
        """Load stage defined in both - raise a warning for now"""
        mock_response = Mock(**mockargs)

        stage_includes = [{"stages": fake_stages}]

        newtest = deepcopy(fulltest)
        newtest["includes"] = stage_includes
        newtest["stages"].insert(0, {"type": "ref", "id": "my_external_stage"})

        includes = dataclasses.replace(includes, stages=fake_stages)

        with pytest.raises(exceptions.DuplicateStageDefinitionError):
            with patch(
                "tavern._plugins.rest.request.requests.Session.request",
                return_value=mock_response,
            ) as pmock:
                run_test("heif", newtest, includes)

        assert not pmock.called

    def test_neither(self, fulltest, mockargs, includes, fake_stages):
        """Raises error if not defined"""
        mock_response = Mock(**mockargs)

        stage_includes = []

        newtest = deepcopy(fulltest)
        newtest["includes"] = stage_includes
        newtest["stages"].insert(0, {"type": "ref", "id": "my_external_stage"})

        with pytest.raises(exceptions.InvalidStageReferenceError):
            with patch(
                "tavern._plugins.rest.request.requests.Session.request",
                return_value=mock_response,
            ):
                run_test("heif", newtest, includes)


class TestRetry:
    def test_repeats_twice_and_succeeds(self, fulltest, mockargs, includes):
        fulltest["stages"][0]["max_retries"] = 1
        failed_mockargs = deepcopy(mockargs)
        failed_mockargs["status_code"] = 400

        mock_responses = [Mock(**failed_mockargs), Mock(**mockargs)]

        with patch(
            "tavern._plugins.rest.request.requests.Session.request",
            side_effect=mock_responses,
        ) as pmock:
            run_test("heif", fulltest, includes)

        assert pmock.call_count == 2

    def test_repeats_twice_and_fails(self, fulltest, mockargs, includes):
        fulltest["stages"][0]["max_retries"] = 1
        mockargs["status_code"] = 400
        mock_response = Mock(**mockargs)

        with patch(
            "tavern._plugins.rest.request.requests.Session.request",
            return_value=mock_response,
        ) as pmock:
            with pytest.raises(exceptions.TestFailError):
                run_test("heif", fulltest, includes)

        assert pmock.call_count == 2

    def test_run_once(self, fulltest, mockargs, includes):
        mock_responses = Mock(**mockargs)

        with patch(
            "tavern._plugins.rest.request.requests.Session.request",
            return_value=mock_responses,
        ) as pmock:
            run_test("heif", fulltest, includes)

        assert pmock.call_count == 1


class TestDelay:
    def test_sleep_before(self, fulltest, mockargs, includes):
        """Should sleep with delay_before in stage spec"""

        fulltest["stages"][0]["delay_before"] = 2

        mock_response = Mock(**mockargs)

        with patch(
            "tavern._plugins.rest.request.requests.Session.request",
            return_value=mock_response,
        ) as pmock:
            with patch("tavern._core.testhelpers.time.sleep") as smock:
                run_test("heif", fulltest, includes)

        assert pmock.called
        smock.assert_called_with(2)

    def test_sleep_after(self, fulltest, mockargs, includes):
        """Should sleep with delay_after in stage spec"""

        fulltest["stages"][0]["delay_after"] = 2

        mock_response = Mock(**mockargs)

        with patch(
            "tavern._plugins.rest.request.requests.Session.request",
            return_value=mock_response,
        ) as pmock:
            with patch("tavern._core.testhelpers.time.sleep") as smock:
                run_test("heif", fulltest, includes)

        assert pmock.called
        smock.assert_called_with(2)


class TestTavernMetaFormat:
    def test_format_env_keys(self, fulltest, mockargs, includes):
        """Should be able to get variables from the environment and use them in
        test responses"""

        env_key = "SPECIAL_CI_MAGIC_COMMIT_TAG"

        fulltest["stages"][0]["request"]["params"] = {
            "a_format_key": f"{{tavern.env_vars.{env_key}}}"
        }

        mock_response = Mock(**mockargs)

        with patch(
            "tavern._plugins.rest.request.requests.Session.request",
            return_value=mock_response,
        ) as pmock:
            with patch.dict(os.environ, {env_key: "bleuihg"}):
                run_test("heif", fulltest, includes)

        assert pmock.called

    def test_format_env_keys_missing_failure(self, fulltest, mockargs, includes):
        """Fails if key is not present"""

        env_key = "SPECIAL_CI_MAGIC_COMMIT_TAG"

        fulltest["stages"][0]["request"]["params"] = {
            "a_format_key": f"{{tavern.env_vars.{env_key}}}"
        }

        with pytest.raises(exceptions.MissingFormatError):
            run_test("heif", fulltest, includes)


class TestFormatRequestVars:
    @pytest.mark.parametrize("request_key", ("params", "json", "headers"))
    def test_format_request_var_dict(self, fulltest, mockargs, includes, request_key):
        """Variables from request should be available to format in response"""

        sent_value = str(uuid.uuid4())

        fulltest["stages"][0]["request"]["method"] = "POST"
        fulltest["stages"][0]["request"][request_key] = {"a_format_key": sent_value}

        if request_key == "json":
            resp_key = "json"
            mockargs[request_key] = lambda: {"returned": sent_value}
        else:
            resp_key = request_key
            mockargs[request_key] = {"returned": sent_value}

        fulltest["stages"][0]["response"][resp_key] = {
            "returned": f"{{tavern.request_vars.{request_key}.a_format_key:s}}"
        }

        mock_response = Mock(**mockargs)

        with patch(
            "tavern._plugins.rest.request.requests.Session.request",
            return_value=mock_response,
        ) as pmock:
            run_test("heif", fulltest, includes)

        assert pmock.called

    @pytest.mark.parametrize("request_key", ("url", "method"))
    def test_format_request_var_value(self, fulltest, mockargs, includes, request_key):
        """Variables from request should be available to format in response"""

        sent_value = str(uuid.uuid4())

        fulltest["stages"][0]["request"]["method"] = "POST"
        fulltest["stages"][0]["request"][request_key] = sent_value

        resp_key = request_key
        mockargs[request_key] = {"returned": sent_value}

        fulltest["stages"][0]["response"][resp_key] = {
            "returned": f"{{tavern.request_vars.{request_key}:s}}"
        }

        mock_response = Mock(**mockargs)

        with (
            patch(
                "tavern._plugins.rest.request.requests.Session.request",
                return_value=mock_response,
            ) as pmock,
            patch(
                "tavern._plugins.rest.request.valid_http_methods", ["POST", sent_value]
            ),
        ):
            run_test("heif", fulltest, includes)

        assert pmock.called


class TestFormatMQTTVarsJson:
    """Test that formatting request vars from mqtt works as well, with json payload"""

    @pytest.fixture(name="fulltest")
    def fix_mqtt_publish_test(self):
        spec = {
            "test_name": "An mqtt test with a single stage",
            "paho-mqtt": {
                "connect": {"host": "localhost"},
            },
            "stages": [
                {
                    "name": "step 1",
                    "mqtt_publish": {
                        "topic": "/abc/123",
                        "json": {"message": str(uuid.uuid4())},
                    },
                    "mqtt_response": {
                        "topic": "{tavern.request_vars.topic}",
                        "json": {"echo": "{tavern.request_vars.json.message}"},
                    },
                }
            ],
        }

        return spec

    def test_format_request_var_dict(self, fulltest, includes):
        """Variables from request should be available to format in response -
        this is the original keys in the input file, NOT the formatted ones
        where 'json' is converted to 'payload' in the actual MQTT publish"""

        stage = fulltest["stages"][0]
        sent = stage["mqtt_publish"]["json"]

        mockargs = {
            "spec": paho.MQTTMessage,
            "payload": json.dumps({"echo": sent["message"]}).encode("utf8"),
            "topic": stage["mqtt_publish"]["topic"],
            "timestamp": 0,
        }
        mock_response = Mock(**mockargs)

        fake_client = MagicMock(
            spec=MQTTClient,
            message_received=Mock(return_value=mock_response),
        )

        with patch(
            "tavern._core.run.get_extra_sessions",
            return_value={"paho-mqtt": fake_client},
        ) as pmock:
            run_test("heif", fulltest, includes)

        assert pmock.called


class TestFormatMQTTVarsPlain:
    """Test that formatting request vars from mqtt works as well, with normal payload"""

    @pytest.fixture(name="fulltest")
    def fix_mqtt_publish_test(self):
        spec = {
            "test_name": "An mqtt test with a single stage",
            "paho-mqtt": {
                "connect": {"host": "localhost"},
            },
            "stages": [
                {
                    "name": "step 1",
                    "mqtt_publish": {"topic": "/abc/123", "payload": "hello"},
                    "mqtt_response": {
                        "topic": "{tavern.request_vars.topic}",
                        "payload": "{tavern.request_vars.payload}",
                    },
                }
            ],
        }

        return spec

    def test_format_request_var_value(self, fulltest, includes):
        """Same as above but with plain keys"""
        stage = fulltest["stages"][0]
        sent = stage["mqtt_publish"]["payload"]

        mockargs = {
            "spec": paho.MQTTMessage,
            "payload": sent.encode("utf8"),
            "topic": stage["mqtt_publish"]["topic"],
            "timestamp": 0,
        }
        mock_response = Mock(**mockargs)

        fake_client = MagicMock(
            spec=MQTTClient, message_received=Mock(return_value=mock_response)
        )

        with patch(
            "tavern._core.run.get_extra_sessions",
            return_value={"paho-mqtt": fake_client},
        ) as pmock:
            run_test("heif", fulltest, includes)

        assert pmock.called


class TestFinally:
    @staticmethod
    def run_test(fulltest, mockargs, includes):
        mock_response = Mock(**mockargs)

        with patch(
            "tavern._plugins.rest.request.requests.Session.request",
            return_value=mock_response,
        ) as pmock:
            run_test("heif", fulltest, includes)

        assert pmock.called

        return pmock

    @pytest.mark.parametrize("finally_block", ([],))
    def test_nop(self, fulltest, mockargs, includes, finally_block):
        """ignore empty finally blocks"""
        fulltest["finally"] = finally_block

        self.run_test(fulltest, mockargs, includes)

    @pytest.mark.parametrize(
        "finally_block",
        (
            {},
            "hi",
            3,
        ),
    )
    def test_wrong_type(self, fulltest, mockargs, includes, finally_block):
        """final stages need to be dicts too"""
        fulltest["finally"] = finally_block

        with pytest.raises(exceptions.BadSchemaError):
            self.run_test(fulltest, mockargs, includes)

    @pytest.fixture
    def finally_request(self):
        return {
            "name": "step 1",
            "request": {"url": "http://www.myfinal.com", "method": "POST"},
            "response": {
                "status_code": 200,
                "json": {"key": "value"},
                "headers": {"content-type": "application/json"},
            },
        }

    def test_finally_run(self, fulltest, mockargs, includes, finally_request):
        fulltest["finally"] = [finally_request]

        pmock = self.run_test(fulltest, mockargs, includes)

        assert pmock.call_count == 2
        assert pmock.mock_calls[1].kwargs.items() >= finally_request["request"].items()

    def test_finally_run_twice(self, fulltest, mockargs, includes, finally_request):
        fulltest["finally"] = [finally_request, finally_request]

        pmock = self.run_test(fulltest, mockargs, includes)

        assert pmock.call_count == 3
        assert pmock.mock_calls[1].kwargs.items() >= finally_request["request"].items()
        assert pmock.mock_calls[2].kwargs.items() >= finally_request["request"].items()

    def test_finally_run_on_main_failure(
        self, fulltest, mockargs, includes, finally_request
    ):
        fulltest["finally"] = [finally_request]

        mockargs["status_code"] = 503

        mock_response = Mock(**mockargs)

        with patch(
            "tavern._plugins.rest.request.requests.Session.request",
            return_value=mock_response,
        ) as pmock:
            with pytest.raises(exceptions.TestFailError):
                run_test("heif", fulltest, includes)

        assert pmock.call_count == 2
        assert pmock.mock_calls[1].kwargs.items() >= finally_request["request"].items()


class TestTinctures:
    @pytest.mark.parametrize(
        "tinctures",
        (
            {"function": "abc"},
            [{"function": "abc"}],
            [{"function": "abc"}, {"function": "def"}],
        ),
    )
    @pytest.mark.parametrize(
        "at_stage_level",
        (
            True,
            False,
        ),
    )
    def test_tinctures(
        self,
        fulltest,
        mockargs,
        includes,
        tinctures,
        at_stage_level,
    ):
        if at_stage_level:
            fulltest["tinctures"] = tinctures
        else:
            fulltest["stages"][0]["tinctures"] = tinctures

        mock_response = Mock(**mockargs)

        tincture_func_mock = Mock()

        with (
            patch(
                "tavern._plugins.rest.request.requests.Session.request",
                return_value=mock_response,
            ) as pmock,
            patch(
                "tavern._core.tincture.get_wrapped_response_function",
                return_value=tincture_func_mock,
            ),
        ):
            run_test("heif", fulltest, includes)

        assert pmock.call_count == 1
        assert tincture_func_mock.call_count == len(tinctures)


def test_copy_config(pytestconfig):
    cfg_1 = load_global_cfg(pytestconfig)

    cfg_1.variables["test1"] = "abc"

    cfg_2 = load_global_cfg(pytestconfig)

    assert cfg_2.variables.get("test1") is None


class TestHooks:
    def test_before_every_request_hook_called(self, fulltest, mockargs, includes):
        """Verify that the before_every_request hook is called"""
        mock_response = Mock(**mockargs)

        def call_func(request_args):
            request_args["headers"] = {"foo": "myzclqkptpk"}

        # Mock the hook caller
        hook_mock = Mock(side_effect=call_func)
        includes.tavern_internal.pytest_hook_caller.pytest_tavern_beta_before_every_request = hook_mock

        with patch(
            "tavern._plugins.rest.request.requests.Session.request",
            return_value=mock_response,
        ):
            run_test("test_file_name", fulltest, includes)

        # Verify the hook was called with the request arguments
        hook_mock.assert_called_once()

        # Verify the request args passed to hook contain the expected values
        request_args = hook_mock.call_args[1]["request_args"]
        assert "url" in request_args
        assert "method" in request_args
        assert request_args["method"] == "GET"
        assert "http://www.google.com" in request_args["url"]

        assert request_args["headers"] == {"foo": "myzclqkptpk"}


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
    ],
)
def test_format_test_marks(marks, expected):
    from tavern._core.pytest.file import _format_test_marks

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
    from tavern._core import exceptions
    from tavern._core.pytest.file import _format_test_marks

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
