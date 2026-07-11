from __future__ import annotations

from typing import Any

from app.autodev.autonomous_manager import AutonomousManager


class AutonomousExecutor:
    """
    Thin execution layer for the autonomous AutoDev manager.

    It normalizes requests and exposes a small, stable API used by
    commands, services and the main Brain integration.
    """

    def __init__(
        self,
        manager: AutonomousManager | None = None,
    ) -> None:
        self.manager = manager or AutonomousManager()

    def start(
        self,
        *,
        max_cycles: int | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return self.manager.start(
            max_cycles=max_cycles,
            context=context,
        )

    def stop(self) -> dict[str, Any]:
        return self.manager.stop()

    def status(self) -> dict[str, Any]:
        return {
            "success": True,
            "status": "STATUS",
            "manager": self.manager.status(),
        }

    def configure(
        self,
        *,
        max_cycles: int,
        stop_on_failure: bool = True,
        stop_when_code_required: bool = True,
    ) -> dict[str, Any]:
        return self.manager.configure(
            max_cycles=max_cycles,
            stop_on_failure=stop_on_failure,
            stop_when_code_required=stop_when_code_required,
        )

    def execute(
        self,
        action: str,
        *,
        context: dict[str, Any] | None = None,
        max_cycles: int | None = None,
    ) -> dict[str, Any]:
        normalized = str(action).strip().casefold()

        if normalized in {"start", "run", "uruchom"}:
            return self.start(
                max_cycles=max_cycles,
                context=context,
            )

        if normalized in {"stop", "zatrzymaj"}:
            return self.stop()

        if normalized in {"status", "stan"}:
            return self.status()

        return {
            "success": False,
            "status": "UNKNOWN_ACTION",
            "action": action,
        }
