from typing import Any, Optional


class StageRegistry:
    def __init__(self, stages: list[dict[str, Any]]):
        self._stages: dict[str, dict] = {}
        for stage in stages:
            stage_id = stage.get("id")
            if stage_id:
                self._stages[stage_id] = stage

    def get_stage(self, stage_id: str) -> Optional[dict]:
        return self._stages.get(stage_id)

    def has_stage(self, stage_id: str) -> bool:
        return stage_id in self._stages

    def get_all_stages(self) -> dict[str, dict]:
        return self._stages.copy()
