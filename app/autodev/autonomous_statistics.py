from __future__ import annotations

from typing import Any


class AutonomousStatistics:

    def __init__(self) -> None:
        self.cycles = 0
        self.successful = 0
        self.failed = 0
        self.stopped = 0

    def update(self, result: dict[str, Any]) -> dict[str, Any]:
        self.cycles += 1

        if result.get("success", False):
            self.successful += 1
        else:
            self.failed += 1

        if str(result.get("status", "")).upper() == "STOPPED":
            self.stopped += 1

        return self.summary()

    def summary(self) -> dict[str, Any]:
        return {
            "cycles": self.cycles,
            "successful": self.successful,
            "failed": self.failed,
            "stopped": self.stopped,
            "success_rate": (
                round(self.successful / self.cycles, 4)
                if self.cycles
                else 0.0
            ),
        }
