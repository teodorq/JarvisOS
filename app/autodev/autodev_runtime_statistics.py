from __future__ import annotations

from typing import Any


class AutoDevRuntimeStatistics:
    def __init__(self) -> None:
        self.cycles_started = 0
        self.cycles_completed = 0
        self.cycles_failed = 0
        self.last_status = "IDLE"

    def started(self) -> None:
        self.cycles_started += 1
        self.last_status = "RUNNING"

    def finished(
        self,
        success: bool,
        status: str,
    ) -> None:

        if success:
            self.cycles_completed += 1
        else:
            self.cycles_failed += 1

        self.last_status = str(status)

    def status(self) -> dict[str, Any]:
        total_finished = (
            self.cycles_completed
            + self.cycles_failed
        )

        return {
            "cycles_started": self.cycles_started,
            "cycles_completed": self.cycles_completed,
            "cycles_failed": self.cycles_failed,
            "last_status": self.last_status,
            "success_rate": (
                round(
                    self.cycles_completed
                    / total_finished,
                    4,
                )
                if total_finished
                else 0.0
            ),
        }
