from tavern._core.starlark.starlark_env import StageResponse


class TestCreateResponseStruct:
    def test_create_response_dict_has_status_code(self, basic_runner, mock_response):
        response = StageResponse(
            success=True,
            response=mock_response,
            request_vars={},
            stage_name="test_stage",
        )
        result = basic_runner._create_response_struct(response)
        assert "status_code" in result
        assert result["status_code"] == 200

    def test_create_response_dict_has_failed(self, basic_runner):
        response = StageResponse(
            success=False,
            response=None,
            request_vars={},
            stage_name="test_stage",
        )
        result = basic_runner._create_response_struct(response)
        assert "failed" in result
        assert result["failed"] is True

    def test_create_response_dict_has_success(self, basic_runner):
        response = StageResponse(
            success=True,
            response=None,
            request_vars={},
            stage_name="test_stage",
        )
        result = basic_runner._create_response_struct(response)
        assert "success" in result
        assert result["success"] is True

    def test_create_response_dict_has_body(self, basic_runner, mock_response):
        response = StageResponse(
            success=True,
            response=mock_response,
            request_vars={},
            stage_name="test_stage",
        )
        result = basic_runner._create_response_struct(response)
        assert "body" in result

    def test_create_response_dict_has_request_vars(self, basic_runner):
        response = StageResponse(
            success=True,
            response=None,
            request_vars={"token": "abc"},
            stage_name="test_stage",
        )
        result = basic_runner._create_response_struct(response)
        assert "request_vars" in result

    def test_create_response_dict_has_stage_name(self, basic_runner):
        response = StageResponse(
            success=True,
            response=None,
            request_vars={},
            stage_name="my_stage",
        )
        result = basic_runner._create_response_struct(response)
        assert "stage_name" in result
        assert result["stage_name"] == "my_stage"
