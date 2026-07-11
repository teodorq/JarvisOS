from __future__ import annotations

from typing import Any


class AutonomousMonitor:

    CRITICAL_STATUSES = {
        "FAILED",
        "PLANNING_FAILED",
        "EXECUTION_EXCEPTION",
        "ROLLBACK_FAILED",
        "FAILED_AND_ROLLED_BACK",
    }

    def inspect(self, result: dict[str, Any]) -> dict[str, Any]:
        status = str(result.get("status", "UNKNOWN"))
        stop_reason = str(result.get("stop_reason", ""))

        alerts: list[str] = []

        if status.upper() in self.CRITICAL_STATUSES:
            alerts.append(f"Krytyczny status: {status}")

        if stop_reason.upper() in self.CRITICAL_STATUSES:
            alerts.append(f"Krytyczny powód zatrzymania: {stop_reason}")

        return {
            "healthy": not alerts,
            "status": status,
            "stop_reason": stop_reason,
            "alerts": alerts,
        }
