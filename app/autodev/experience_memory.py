from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class ExperienceRecord:
    success: bool
    status: str
    goal: str = ""
    task_id: str = ""
    target: str = ""
    errors: list[str] = field(default_factory=list)
    lessons: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "status": self.status,
            "goal": self.goal,
            "task_id": self.task_id,
            "target": self.target,
            "errors": list(self.errors),
            "lessons": list(self.lessons),
            "metadata": dict(self.metadata),
            "created_at": self.created_at,
        }


class ExperienceMemory:

    def __init__(self, max_records: int = 1000) -> None:
        self.max_records = max(1, int(max_records))
        self.records: list[ExperienceRecord] = []

    def remember(
        self,
        *,
        success: bool,
        status: str,
        goal: str = "",
        task_id: str = "",
        target: str = "",
        errors: list[str] | None = None,
        lessons: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> ExperienceRecord:
        record = ExperienceRecord(
            success=bool(success),
            status=str(status),
            goal=str(goal),
            task_id=str(task_id),
            target=str(target),
            errors=list(errors or []),
            lessons=list(lessons or []),
            metadata=dict(metadata or {}),
        )
        self.records.append(record)
        if len(self.records) > self.max_records:
            self.records = self.records[-self.max_records:]
        return record

    def last(self) -> ExperienceRecord | None:
        return self.records[-1] if self.records else None

    def summary(self) -> dict[str, Any]:
        total = len(self.records)
        successful = sum(1 for item in self.records if item.success)
        failed = total - successful
        return {
            "total": total,
            "successful": successful,
            "failed": failed,
            "success_rate": round(successful / total, 4) if total else 0.0,
            "last": self.last().to_dict() if self.last() else None,
        }
