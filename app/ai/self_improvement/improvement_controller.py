from __future__ import annotations

from typing import Any

from app.ai.self_improvement.improvement_brain import (
    ImprovementBrain,
)
from app.ai.self_improvement.improvement_memory import (
    ImprovementMemory,
)


class ImprovementController:

    TERMINAL_STATUSES = {
        "COMPLETED",
        "NO_ACTION",
        "FAILED",
    }

    def __init__(
        self,
        project_root: str = "C:/JarvisAI",
        improvement_brain: ImprovementBrain | None = None,
        improvement_memory: ImprovementMemory | None = None,
        research_service: Any | None = None,
        reasoning_service: Any | None = None,
        evolution_controller: Any | None = None,
        continuous_dev_controller: Any | None = None,
    ) -> None:

        self.project_root = str(
            project_root
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

        normalized_command = str(
            command
        ).strip()

        if not normalized_command:
            return {
                "success": False,
                "status": "EMPTY_COMMAND",
                "error": (
                    "Polecenie Self Improvement jest puste."
                ),
            }

        lowered = normalized_command.lower()
        normalized_context = self._safe_dict(
            context
        )

        analyze_prefixes = (
            "self improvement analyze ",
            "self improvement start ",
            "improvement brain analyze ",
            "improvement brain start ",
            "samodoskonalenie analizuj ",
            "samodoskonalenie start ",
            "ulepsz siebie ",
            "przeanalizuj własny rozwój ",
            "przeanalizuj wlasny rozwoj ",
        )

        for prefix in analyze_prefixes:
            if lowered.startswith(
                prefix
            ):
                objective = normalized_command[
                    len(prefix):
                ].strip()

                return self.analyze(
                    objective=objective,
                    project_context=normalized_context,
                    auto_execute=False,
                    mode="SAFE_AUTONOMOUS",
                )

        autonomous_prefixes = (
            "self improvement autonomous ",
            "improvement brain autonomous ",
            "samodoskonalenie autonomiczne ",
            "autonomicznie ulepsz siebie ",
        )

        for prefix in autonomous_prefixes:
            if lowered.startswith(
                prefix
            ):
                objective = normalized_command[
                    len(prefix):
                ].strip()

                return self.analyze(
                    objective=objective,
                    project_context=normalized_context,
                    auto_execute=True,
                    approved=True,
                    mode="AUTONOMOUS",
                )

        safe_auto_prefixes = (
            "self improvement safe ",
            "improvement brain safe ",
            "bezpiecznie ulepsz siebie ",
        )

        for prefix in safe_auto_prefixes:
            if lowered.startswith(
                prefix
            ):
                objective = normalized_command[
                    len(prefix):
                ].strip()

                return self.analyze(
                    objective=objective,
                    project_context=normalized_context,
                    auto_execute=True,
                    approved=None,
                    mode="SAFE_AUTONOMOUS",
                )

        execute_prefixes = (
            "self improvement execute ",
            "improvement brain execute ",
            "samodoskonalenie wykonaj ",
        )

        for prefix in execute_prefixes:
            if lowered.startswith(
                prefix
            ):
                session_id = normalized_command[
                    len(prefix):
                ].strip()

                return self.execute_session(
                    session_id=session_id,
                    approved=None,
                    context=normalized_context,
                )

        approve_prefixes = (
            "self improvement approve ",
            "improvement brain approve ",
            "samodoskonalenie zaakceptuj ",
        )

        for prefix in approve_prefixes:
            if lowered.startswith(
                prefix
            ):
                session_id = normalized_command[
                    len(prefix):
                ].strip()

                return self.approve_session(
                    session_id=session_id,
                    approved=True,
                    context=normalized_context,
                )

        reject_prefixes = (
            "self improvement reject ",
            "improvement brain reject ",
            "samodoskonalenie odrzuć ",
            "samodoskonalenie odrzuc ",
        )

        for prefix in reject_prefixes:
            if lowered.startswith(
                prefix
            ):
                session_id = normalized_command[
                    len(prefix):
                ].strip()

                return self.approve_session(
                    session_id=session_id,
                    approved=False,
                    context=normalized_context,
                )

        status_prefixes = (
            "self improvement status ",
            "improvement brain status ",
            "samodoskonalenie status ",
        )

        for prefix in status_prefixes:
            if lowered.startswith(
                prefix
            ):
                session_id = normalized_command[
                    len(prefix):
                ].strip()

                session = self.get_session(
                    session_id
                )

                if session is None:
                    return {
                        "success": False,
                        "status": "NOT_FOUND",
                        "session_id": session_id,
                    }

                return {
                    "success": True,
                    "status": "FOUND",
                    "session_id": session_id,
                    "session": session,
                }

        if lowered in {
            "self improvement list",
            "improvement brain list",
            "samodoskonalenie lista",
        }:
            return {
                "success": True,
                "status": "COMPLETED",
                "sessions": self.list_sessions(),
            }

        if lowered in {
            "self improvement summary",
            "improvement brain summary",
            "samodoskonalenie podsumowanie",
        }:
            return {
                "success": True,
                "status": "COMPLETED",
                "summary": self.system_summary(),
            }

        if lowered in {
            "self improvement memory",
            "improvement brain memory",
            "samodoskonalenie pamięć",
            "samodoskonalenie pamiec",
        }:
            return {
                "success": True,
                "status": "COMPLETED",
                "memory_summary": self.memory_summary(),
            }

        return {
            "success": False,
            "status": "UNKNOWN_COMMAND",
            "command": normalized_command,
            "error": (
                "Nie rozpoznano polecenia Self Improvement."
            ),
        }

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
