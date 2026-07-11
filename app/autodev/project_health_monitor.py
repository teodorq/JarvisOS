from __future__ import annotations

from typing import Any


class ProjectHealthMonitor:

    def __init__(self) -> None:
        self.last_report: dict[str, Any] | None = None

    def analyze(self) -> dict[str, Any]:

        report = {
            "healthy": True,
            "issues": [],
            "suggestions": [
                "Review Brain",
                "Review AutoDev",
                "Review Memory",
                "Review Vision",
            ],
        }

        self.last_report = report
        return report

    def get_last_report(self) -> dict[str, Any] | None:
        return self.last_report