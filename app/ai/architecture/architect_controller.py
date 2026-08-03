from __future__ import annotations

from pathlib import Path
from typing import Any

from .autonomous_architect import AutonomousArchitect


class ArchitectController:

    def __init__(
        self,
        project_root: str | Path,
        *,
        evolution_controller: object | None = None,
        director_controller: object | None = None,
        task_queue: object | None = None,
    ) -> None:
        self.architect = AutonomousArchitect(
            project_root=project_root,
            evolution_controller=evolution_controller,
            director_controller=director_controller,
            task_queue=task_queue,
        )

    def run(
        self,
        *,
        enqueue: bool = True,
        limit: int = 10,
    ) -> dict[str, Any]:
        return self.architect.analyze_and_plan(
            enqueue=enqueue,
            limit=limit,
        )

    def handle(
        self,
        command: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        normalized = " ".join(
            str(command).lower().split()
        )
        context = dict(context or {})

        if not self.can_handle(normalized):
            return {
                "success": False,
                "status": "UNSUPPORTED_COMMAND",
            }

        return self.run(
            enqueue=bool(
                context.get("enqueue", True)
            ),
            limit=max(
                1,
                int(context.get("limit", 10)),
            ),
        )

    @staticmethod
    def can_handle(
        command: str,
    ) -> bool:
        normalized = " ".join(
            str(command).lower().split()
        )

        phrases = (
            "architect ai",
            "autonomous architect",
            "analizuj architekturę",
            "analizuj architekture",
            "zaplanuj refaktoryzację",
            "zaplanuj refaktoryzacje",
        )

        return any(
            phrase in normalized
            for phrase in phrases
        )
