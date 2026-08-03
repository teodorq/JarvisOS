"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations

from .improvement_command_router import ImprovementCommandRouter

from app.core.project_paths import default_project_root

from typing import Any

from app.ai.self_improvement.improvement_brain import (
    ImprovementBrain,
)
from app.ai.self_improvement.improvement_memory import (
    ImprovementMemory,
)


_IMPROVEMENT_COMMAND_ROUTER = ImprovementCommandRouter()


class ImprovementController:

    TERMINAL_STATUSES = {
        "COMPLETED",
        "NO_ACTION",
        "FAILED",
    }

    def __init__(
        self,
        project_root: str | None = None,
        improvement_brain: ImprovementBrain | None = None,
        improvement_memory: ImprovementMemory | None = None,
        research_service: Any | None = None,
        reasoning_service: Any | None = None,
        evolution_controller: Any | None = None,
        continuous_dev_controller: Any | None = None,
    ) -> None:

        self.project_root = str(
            project_root
            or default_project_root()
        ).strip()

        if not self.project_root:
            raise ValueError(
                "ImprovementController wymaga project_root."
            )

        self.improvement_memory = (
            improvement_memory
            if improvement_memory is not None
            else ImprovementMemory()
        )

        self.improvement_brain = (
            improvement_brain
            if improvement_brain is not None
            else ImprovementBrain(
                project_root=self.project_root,
                research_service=research_service,
                reasoning_service=reasoning_service,
                evolution_controller=evolution_controller,
                continuous_dev_controller=(
                    continuous_dev_controller
                ),
            )
        )

    def analyze(
        self,
        objective: str,
        project_context: dict[str, Any] | None = None,
        auto_execute: bool = False,
        approved: bool | None = None,
        mode: str = "SAFE_AUTONOMOUS",
    ) -> dict[str, Any]:

        result = self.improvement_brain.analyze(
            objective=objective,
            project_context=project_context,
            auto_execute=auto_execute,
            approved=approved,
            mode=mode,
        )

        self._remember_if_terminal(
            result
        )

        return result

    def execute_session(
        self,
        session_id: str,
        approved: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        result = self.improvement_brain.execute(
            session_id=session_id,
            approved=approved,
            context=context,
        )

        self._remember_if_terminal(
            result
        )

        return result

    def approve_session(
        self,
        session_id: str,
        approved: bool,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        result = self.improvement_brain.execute(
            session_id=session_id,
            approved=approved,
            context=context,
        )

        self._remember_if_terminal(
            result
        )

        return result

    def get_session(
        self,
        session_id: str,
    ) -> dict[str, Any] | None:

        return self.improvement_brain.get_session(
            session_id
        )

    def list_sessions(
        self,
        limit: int = 50,
    ) -> list[dict[str, Any]]:

        return self.improvement_brain.list_sessions(
            limit=limit
        )

    def memory_summary(
        self,
    ) -> dict[str, Any]:

        return self.improvement_memory.summary()

    def system_summary(
        self,
    ) -> dict[str, Any]:

        return {
            "sessions": self.list_sessions(
                limit=100
            ),
            "memory": self.improvement_memory.summary(),
            "project_root": self.project_root,
            "controller_version": "1.0.0",
        }

    def handle(
        self,
        command: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return _IMPROVEMENT_COMMAND_ROUTER.handle(
            self,
            command,
            context,
        )

    def can_handle(
        self,
        command: str,
    ) -> bool:

        normalized = str(
            command
        ).strip().lower()

        prefixes = (
            "self improvement ",
            "improvement brain ",
            "samodoskonalenie ",
            "ulepsz siebie ",
            "przeanalizuj własny rozwój ",
            "przeanalizuj wlasny rozwoj ",
            "autonomicznie ulepsz siebie ",
            "bezpiecznie ulepsz siebie ",
        )

        return normalized.startswith(
            prefixes
        )

    def _remember_if_terminal(
        self,
        result: dict[str, Any],
    ) -> None:

        if not isinstance(
            result,
            dict,
        ):
            return

        status = str(
            result.get(
                "status",
                "",
            )
        ).upper()

        if status not in self.TERMINAL_STATUSES:
            return

        session_id = str(
            result.get(
                "session_id",
                "",
            )
        ).strip()

        if not session_id:
            return

        session = self.improvement_brain.get_session(
            session_id
        )

        if session is None:
            session = dict(
                result
            )

        existing = self.improvement_memory.get(
            session_id
        )

        if existing is None:
            self.improvement_memory.remember(
                session=session,
                result=result,
            )

            return

        execution = self._safe_dict(
            result.get(
                "execution",
                {},
            )
        )

        self.improvement_memory.update(
            session_id=session_id,
            status=status,
            decision=result.get(
                "decision"
            ),
            execution_status=execution.get(
                "status"
            ),
            lessons=self._safe_string_list(
                result.get(
                    "lessons",
                    [],
                )
            ),
            errors=self._safe_string_list(
                result.get(
                    "errors",
                    [],
                )
            ),
            warnings=self._safe_string_list(
                result.get(
                    "warnings",
                    [],
                )
            ),
            metadata={
                "updated_by": "ImprovementController",
            },
        )

    def _safe_dict(
        self,
        value: Any,
    ) -> dict[str, Any]:

        if isinstance(
            value,
            dict,
        ):
            return dict(
                value
            )

        return {}

    def _safe_list(
        self,
        value: Any,
    ) -> list[Any]:

        if isinstance(
            value,
            list,
        ):
            return list(
                value
            )

        if isinstance(
            value,
            tuple,
        ):
            return list(
                value
            )

        if isinstance(
            value,
            set,
        ):
            return list(
                value
            )

        if value is None:
            return []

        return [
            value
        ]

    def _safe_string_list(
        self,
        value: Any,
    ) -> list[str]:

        result: list[str] = []
        seen: set[str] = set()

        for item in self._safe_list(
            value
        ):
            text = str(
                item
            ).strip()

            if not text:
                continue

            key = text.lower()

            if key in seen:
                continue

            seen.add(
                key
            )
            result.append(
                text
            )

        return result
