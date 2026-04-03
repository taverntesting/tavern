from tavern._core.starlark.starlark_env import StageResponse, StarlarkPipelineRunner


class TestStageResponseStruct:
    def test_stage_response_has_status_code_in_response(self):
        response = StageResponse(
            success=True,
            response={"status_code": 200, "body": {"foo": "bar"}},
            request_vars={},
            stage_name="test_stage",
        )
        starlark_obj = response.to_starlark()
        assert "status_code" in starlark_obj["response"]

    def test_stage_response_has_failed_not_in_response(self):
        response = StageResponse(
            success=False,
            response={"status_code": 500, "error": "server error"},
            request_vars={},
            stage_name="test_stage",
        )
        starlark_obj = response.to_starlark()
        assert "failed" not in starlark_obj["response"]

    def test_stage_response_has_success_field(self):
        response = StageResponse(
            success=True,
            response={"status_code": 200},
            request_vars={},
            stage_name="test_stage",
        )
        starlark_obj = response.to_starlark()
        assert "success" in starlark_obj

    def test_stage_response_has_body_in_response(self):
        response = StageResponse(
            success=True,
            response={"status_code": 200, "body": {"data": "test"}},
            request_vars={},
            stage_name="test_stage",
        )
        starlark_obj = response.to_starlark()
        assert "response" in starlark_obj

    def test_stage_response_has_request_vars(self):
        response = StageResponse(
            success=True,
            response={"status_code": 200},
            request_vars={"var": "value"},
            stage_name="test_stage",
        )
        starlark_obj = response.to_starlark()
        assert "request_vars" in starlark_obj


class TestCreateResponseStruct:
    def test_create_response_dict_has_status_code(self):
        runner = StarlarkPipelineRunner(test_path="/fake/path")
        response = StageResponse(
            success=True,
            response={"status_code": 200, "body": {"foo": "bar"}},
            request_vars={},
            stage_name="test_stage",
        )
        result = runner._create_response_struct(response)
        assert "status_code" in result
        assert result["status_code"] == 200

    def test_create_response_dict_has_failed(self):
        runner = StarlarkPipelineRunner(test_path="/fake/path")
        response = StageResponse(
            success=False,
            response={"status_code": 500},
            request_vars={},
            stage_name="test_stage",
        )
        result = runner._create_response_struct(response)
        assert "failed" in result
        assert result["failed"] is True

    def test_create_response_dict_has_success(self):
        runner = StarlarkPipelineRunner(test_path="/fake/path")
        response = StageResponse(
            success=True,
            response={"status_code": 200},
            request_vars={},
            stage_name="test_stage",
        )
        result = runner._create_response_struct(response)
        assert "success" in result
        assert result["success"] is True

    def test_create_response_dict_has_body(self):
        runner = StarlarkPipelineRunner(test_path="/fake/path")
        response = StageResponse(
            success=True,
            response={"status_code": 200, "body": {"data": "test"}},
            request_vars={},
            stage_name="test_stage",
        )
        result = runner._create_response_struct(response)
        assert "body" in result

    def test_create_response_dict_has_request_vars(self):
        runner = StarlarkPipelineRunner(test_path="/fake/path")
        response = StageResponse(
            success=True,
            response={"status_code": 200},
            request_vars={"token": "abc"},
            stage_name="test_stage",
        )
        result = runner._create_response_struct(response)
        assert "request_vars" in result

    def test_create_response_dict_has_stage_name(self):
        runner = StarlarkPipelineRunner(test_path="/fake/path")
        response = StageResponse(
            success=True,
            response={"status_code": 200},
            request_vars={},
            stage_name="my_stage",
        )
        result = runner._create_response_struct(response)
        assert "stage_name" in result
        assert result["stage_name"] == "my_stage"
