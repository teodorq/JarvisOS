from __future__ import annotations

from typing import Any

from app.autodev.experience_memory import ExperienceMemory


class LearningEngine:

    def __init__(
        self,
        memory: ExperienceMemory | None = None,
    ) -> None:
        self.memory = memory or ExperienceMemory()

    def learn_from_result(
        self,
        result: dict[str, Any],
    ) -> dict[str, Any]:
        result = dict(result or {})
        generation = result.get("generation")
        if not isinstance(generation, dict):
            generation = {}

        execution = result.get("execution")
        if not isinstance(execution, dict):
            execution = {}

        task = generation.get("task")
        if not isinstance(task, dict):
            task = {}

        source = execution or generation or result

        record = self.memory.remember(
            success=bool(source.get("success", result.get("success", False))),
            status=str(source.get("status", result.get("status", "UNKNOWN"))),
            goal=str(
                task.get(
                    "description",
                    task.get("title", generation.get("goal", "")),
                )
            ),
            task_id=str(task.get("task_id", generation.get("planner_task_id", ""))),
            target=str(task.get("target", "")),
            errors=list(source.get("errors") or []),
            lessons=[
                str(source.get("message"))
            ] if source.get("message") else [],
            metadata={
                "runtime_status": str(result.get("status", "")),
            },
        )

        return {
            "success": True,
            "status": "LEARNED",
            "record": record.to_dict(),
            "memory": self.memory.summary(),
        }

    def summary(self) -> dict[str, Any]:
        return self.memory.summary()
