from __future__ import annotations

from typing import Any

from app.autodev.autodev_runtime_commands import (
    AutoDevRuntimeCommands,
)
from app.autodev.autodev_runtime_service import (
    AutoDevRuntimeService,
)
from app.core.project_paths import resolve_project_root


class AutoDevRuntimeController:
    """
    Kontroler gotowy do podłączenia do Brain.

    Nie zapisuje kodu i nie wykonuje zatwierdzonych zmian.
    """

    def __init__(
        self,
        project_root: str | None = None,
        service: AutoDevRuntimeService | None = None,
        commands: AutoDevRuntimeCommands | None = None,
    ) -> None:

        resolved_root = str(
            resolve_project_root(
                project_root
            )
        )

        self.service = (
            service
            or AutoDevRuntimeService(
                project_root=resolved_root
            )
        )

        self.commands = (
            commands
            or AutoDevRuntimeCommands(
                service=self.service
            )
        )

        self.last_result: dict[str, Any] | None = None

    def can_handle(
        self,
        command: str,
    ) -> bool:

        return self.commands.can_handle(
            command
        )

    def handle(
        self,
        command: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        result = self.commands.handle(
            command
        )

        normalized = {
            **dict(result),
            "controller": "AutoDevRuntimeController",
            "context": dict(context or {}),
        }

        self.last_result = dict(normalized)
        return normalized

    def status(
        self,
    ) -> dict[str, Any]:

        return {
            "controller": "AutoDevRuntimeController",
            "last_result": self.last_result,
            "service": self.service.status(),
        }
