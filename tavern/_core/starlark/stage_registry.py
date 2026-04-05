from typing import Any, Optional

from tavern._core import exceptions


class StageRegistry:
    """Stores all stages which are accessible from starlark (ie, which have an id)"""

    def __init__(self, stages: list[dict[str, Any]]):
        self._stages: dict[str, dict] = {}
        for stage in stages:
            stage_id = stage.get("id")
            if stage_id:
                if stage_id in self._stages:
                    raise exceptions.DuplicateStageDefinitionError(
                        f"Duplicate stage id '{stage_id}' found"
                    )
                self._stages[stage_id] = stage

    def get_stage(self, stage_id: str) -> Optional[dict]:
        return self._stages.get(stage_id)

    def get_all_stages(self) -> dict[str, dict]:
        return self._stages.copy()
