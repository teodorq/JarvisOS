from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any
from uuid import uuid4

from .autonomy_governance_store import AutonomyGovernanceStore
from .autonomy_stage_utils import (
    BackgroundAutonomyStage,
    count_statuses,
    now,
)


class RecoveryLearningService(BackgroundAutonomyStage):
    """B72 evidence-bounded ranking of B70/B71 recovery runbooks."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        store: AutonomyGovernanceStore,
    ) -> None:
        super().__init__(
            project_root,
            store=store,
            stage="B72",
            thread_name="jarvis-b72-recovery-learning",
            default_interval=300.0,
        )

    def run_cycle(self) -> dict[str, Any]:
        executions = list(reversed(self.store.list_records("B71", limit=10000)))
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for item in executions:
            category = str(item.get("category", "UNKNOWN")).upper()
            grouped[category].append(item)

        lessons: list[dict[str, Any]] = []
        policy = self.store.policy("B72")
        minimum = int(policy.get("min_evidence", 3))
        block_threshold = float(policy.get("block_success_rate_below", 0.25))
        unblock_threshold = float(policy.get("unblock_success_rate_at", 0.60))

        for category, values in sorted(grouped.items()):
            completed = sum(
                1 for item in values
                if str(item.get("status", "")).upper() == "COMPLETED"
            )
            attempts = len(values)
            success_rate = completed / attempts if attempts else 0.0
            blocked = attempts >= minimum and success_rate < block_threshold
            if attempts >= minimum and success_rate >= unblock_threshold:
                blocked = False
            runbooks: dict[str, dict[str, Any]] = {}
            for item in values:
                key = " → ".join(str(step) for step in item.get("runbook", []))
                bucket = runbooks.setdefault(
                    key,
                    {"attempts": 0, "completed": 0},
                )
                bucket["attempts"] += 1
                if str(item.get("status", "")).upper() == "COMPLETED":
                    bucket["completed"] += 1
            ranking = sorted(
                (
                    {
                        "runbook": key.split(" → ") if key else [],
                        "attempts": value["attempts"],
                        "completed": value["completed"],
                        "success_rate": (
                            value["completed"] / value["attempts"]
                            if value["attempts"] else 0.0
                        ),
                    }
                    for key, value in runbooks.items()
                ),
                key=lambda item: (
                    -float(item["success_rate"]),
                    -int(item["attempts"]),
                ),
            )
            lessons.append({
                "lesson_id": f"recovery-lesson-{uuid4().hex}",
                "category": category,
                "status": "BLOCKED" if blocked else "ACTIVE",
                "attempts": attempts,
                "completed": completed,
                "success_rate": round(success_rate, 6),
                "blocked": blocked,
                "ranking": ranking[:10],
                "created_at": now(),
            })

        self.store.replace_records("B72", lessons)
        blocked_count = sum(1 for item in lessons if item.get("blocked"))
        return self._finish(
            "RECOVERY_LEARNING_CYCLE_COMPLETED",
            success=True,
            phase="READY",
            decision="LEARN",
            record=lessons[-1] if lessons else None,
            lessons=lessons,
            lesson_counts=count_statuses(lessons),
            blocked_categories=blocked_count,
        )

    def allow_execution(self, plan: dict[str, Any]) -> dict[str, Any]:
        category = str(plan.get("category", "UNKNOWN")).upper()
        for lesson in self.store.list_records("B72", limit=10000):
            if str(lesson.get("category", "")).upper() != category:
                continue
            if bool(lesson.get("blocked", False)):
                return {
                    "allowed": False,
                    "category": category,
                    "reason": (
                        "B72 zablokował runbook po wystarczającej liczbie "
                        "nieudanych prób."
                    ),
                    "lesson": lesson,
                }
            return {
                "allowed": True,
                "category": category,
                "reason": "Runbook ma dopuszczalny profil skuteczności.",
                "lesson": lesson,
            }
        return {
            "allowed": True,
            "category": category,
            "reason": "Brak wystarczających danych do blokady.",
        }

    def status(self) -> dict[str, Any]:
        records = self.store.list_records("B72", limit=100)
        return self._response(
            "RECOVERY_LEARNING_STATUS",
            success=True,
            lessons=records,
            lesson_counts=count_statuses(records),
            blocked_categories=[
                str(item.get("category", ""))
                for item in records
                if bool(item.get("blocked", False))
            ],
        )

    def history(self, *, limit: int = 30) -> dict[str, Any]:
        return self._response(
            "RECOVERY_LEARNING_HISTORY",
            success=True,
            lessons=self.store.list_records("B72", limit=limit),
            history=self.store.history(stage="B72", limit=limit),
        )
