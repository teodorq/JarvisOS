from __future__ import annotations

from typing import Any


class WorkSelector:

    PRIORITY_SCORE = {
        "CRITICAL": 400,
        "HIGH": 300,
        "NORMAL": 200,
        "LOW": 100,
    }

    READY_STATUSES = {
        "PENDING",
        "READY",
        "QUEUED",
        "RETRY",
    }

    def select(
        self,
        tasks: list[dict[str, Any]],
    ) -> dict[str, Any] | None:
        candidates = [
            dict(task)
            for task in tasks
            if str(
                task.get("status", "PENDING")
            ).upper() in self.READY_STATUSES
        ]

        if not candidates:
            return None

        candidates.sort(
            key=self._score,
            reverse=True,
        )

        return candidates[0]

    def _score(
        self,
        task: dict[str, Any],
    ) -> tuple[int, float, str]:
        priority = str(
            task.get("priority", "NORMAL")
        ).upper()

        priority_score = self.PRIORITY_SCORE.get(
            priority,
            0,
        )

        extra_score = float(
            task.get(
                "priority_score",
                0.0,
            )
            or 0.0
        )

        created_at = str(
            task.get(
                "created_at",
                "",
            )
        )

        return (
            priority_score,
            extra_score,
            created_at,
        )
