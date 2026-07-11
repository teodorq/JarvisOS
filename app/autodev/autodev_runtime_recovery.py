from __future__ import annotations

from typing import Any

from app.autodev.autodev_queue_service import (
    AutoDevQueueService,
)


class AutoDevRuntimeRecovery:
    def __init__(
        self,
        queue_service: AutoDevQueueService,
    ) -> None:
        self.queue_service = queue_service
        self.last_result: dict[str, Any] | None = None

    def recover_queue(
        self,
        items: list[dict[str, Any]],
    ) -> dict[str, Any]:
        restored = 0
        skipped = 0

        for item in items:
            if not isinstance(item, dict):
                skipped += 1
                continue

            goal = str(
                item.get(
                    "goal",
                    "",
                )
            ).strip()

            if not goal:
                skipped += 1
                continue

            self.queue_service.enqueue(
                dict(item)
            )
            restored += 1

        result = {
            "success": True,
            "status": "RECOVERY_COMPLETED",
            "restored": restored,
            "skipped": skipped,
            "queue": self.queue_service.status(),
        }

        self.last_result = dict(result)
        return result
