from __future__ import annotations

from typing import Any

from app.autodev.autonomous_service import AutonomousService


class AutonomousAPI:
    """
    Programmatic API for the autonomous AutoDev service.
    """

    def __init__(
        self,
        service: AutonomousService | None = None,
    ) -> None:
        self.service = service or AutonomousService()

    def start(
        self,
        *,
        max_cycles: int | None = None,
        background: bool = True,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.service.start(
            max_cycles=max_cycles,
            background=background,
            context=context,
        )

    def stop(self) -> dict[str, Any]:
        return self.service.stop()

    def status(self) -> dict[str, Any]:
        return self.service.status()

    def stats(self) -> dict[str, Any]:
        manager_status = self.service.executor.manager.status()
        loop = manager_status.get("loop", {})
        return {
            "success": True,
            "status": "STATISTICS",
            "statistics": loop.get("statistics", {}),
        }

    def learning(self) -> dict[str, Any]:
        manager_status = self.service.executor.manager.status()
        loop = manager_status.get("loop", {})
        return {
            "success": True,
            "status": "LEARNING",
            "learning": loop.get("learning", {}),
        }
