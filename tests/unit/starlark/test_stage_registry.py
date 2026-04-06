from tavern._core.starlark.stage_registry import StageRegistry


class TestStageRegistry:
    def test_registry_builds_id_to_stage_map(self):
        stages = [
            {
                "id": "stage1",
                "name": "Stage 1",
                "request": {"url": "http://example.com"},
            },
            {
                "id": "stage2",
                "name": "Stage 2",
                "request": {"url": "http://example.com"},
            },
        ]
        registry = StageRegistry(stages)
        assert registry.get_stage("stage1") is not None
        assert registry.get_stage("stage2") is not None

    def test_registry_ignores_stages_without_id(self):
        stages = [
            {"name": "Stage without ID", "request": {"url": "http://example.com"}},
            {
                "id": "stage_with_id",
                "name": "Stage with ID",
                "request": {"url": "http://example.com"},
            },
        ]
        registry = StageRegistry(stages)
        assert registry.get_stage("stage_with_id") is not None
        assert registry.get_stage("Stage without ID") is None

    def test_registry_returns_none_for_nonexistent_id(self):
        stages = [
            {
                "id": "stage1",
                "name": "Stage 1",
                "request": {"url": "http://example.com"},
            },
        ]
        registry = StageRegistry(stages)
        assert registry.get_stage("nonexistent") is None

    def test_get_all_stages_returns_dict(self):
        stages = [
            {"id": "stage1", "name": "Stage 1"},
            {"id": "stage2", "name": "Stage 2"},
        ]
        registry = StageRegistry(stages)
        all_stages = registry.get_all_stages()
        assert isinstance(all_stages, dict)
        assert "stage1" in all_stages
        assert "stage2" in all_stages
