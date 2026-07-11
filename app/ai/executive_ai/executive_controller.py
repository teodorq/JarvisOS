from __future__ import annotations

from typing import Any

from app.ai.executive_ai.executive_engine import (
    ExecutiveEngine,
)
from app.ai.executive_ai.executive_memory import (
    ExecutiveMemory,
)
from app.ai.executive_ai.executive_planner import (
    ExecutivePlanner,
)


class ExecutiveController:

    def __init__(
        self,
        project_root: str = "C:/JarvisAI",
        executive_engine: ExecutiveEngine | None = None,
        executive_memory: ExecutiveMemory | None = None,
        executive_planner: ExecutivePlanner | None = None,
        project_director: Any | None = None,
        reasoning_service: Any | None = None,
        research_service: Any | None = None,
        improvement_controller: Any | None = None,
        evolution_controller: Any | None = None,
        continuous_dev_controller: Any | None = None,
        autonomous_dev_controller: Any | None = None,
    ) -> None:

        self.project_root = str(
            project_root
        ).strip()

        if not self.project_root:
            raise ValueError(
                "ExecutiveController wymaga project_root."
            )

        self.executive_memory = (
            executive_memory
            if executive_memory is not None
            else ExecutiveMemory()
        )

        self.executive_planner = (
            executive_planner
            if executive_planner is not None
            else ExecutivePlanner()
        )

        self.autonomous_dev_controller = (
            autonomous_dev_controller
        )

        self.executive_engine = (
            executive_engine
            if executive_engine is not None
            else ExecutiveEngine(
                project_root=self.project_root,
                planner=self.executive_planner,
                memory=self.executive_memory,
                project_director=project_director,
                reasoning_service=reasoning_service,
                research_service=research_service,
                improvement_controller=(
                    improvement_controller
                ),
                evolution_controller=(
                    evolution_controller
                ),
                continuous_dev_controller=(
                    continuous_dev_controller
                ),
            )
        )

    def create_session(
        self,
        objective: str,
        mode: str = "SAFE_AUTONOMOUS",
        max_phases: int = 5,
        context: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.executive_engine.create_session(
            objective=objective,
            mode=mode,
            max_phases=max_phases,
            context=context,
            metadata=metadata,
        )

    def start_session(
        self,
        executive_id: str,
        approved: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.executive_engine.start(
            executive_id=executive_id,
            approved=approved,
            context=context,
        )

    def create_and_start(
        self,
        objective: str,
        mode: str = "SAFE_AUTONOMOUS",
        max_phases: int = 5,
        context: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        approved: bool | None = None,
    ) -> dict[str, Any]:

        created = self.create_session(
            objective=objective,
            mode=mode,
            max_phases=max_phases,
            context=context,
            metadata=metadata,
        )

        executive_id = str(
            created.get(
                "executive_id",
                "",
            )
        ).strip()

        if not executive_id:
            return {
                "success": False,
                "status": "FAILED",
                "error": (
                    "ExecutiveController nie otrzymał "
                    "executive_id."
                ),
            }

        result = self.start_session(
            executive_id=executive_id,
            approved=approved,
            context=context,
        )

        if (
            mode == "AUTONOMOUS"
            and result.get("success", False)
        ):
            autodev_result = self._delegate_to_autodev(
                objective=objective,
                context=context,
            )

            result = dict(result)
            result["autodev"] = autodev_result

            if isinstance(autodev_result, dict):
                task_id = str(
                    autodev_result.get(
                        "task_id",
                        autodev_result.get(
                            "autodev_task_id",
                            "",
                        ),
                    )
                ).strip()

                if task_id:
                    result["autodev_task_id"] = task_id

        return result

    def approve_session(
        self,
        executive_id: str,
        approved: bool,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.executive_engine.approve(
            executive_id=executive_id,
            approved=approved,
            context=context,
        )

    def get_session(
        self,
        executive_id: str,
    ) -> dict[str, Any] | None:

        return self.executive_engine.get_session(
            executive_id
        )

    def list_sessions(
        self,
        limit: int = 50,
    ) -> list[dict[str, Any]]:

        return self.executive_engine.list_sessions(
            limit=limit
        )

    def memory_summary(
        self,
    ) -> dict[str, Any]:

        return self.executive_memory.summary()

    def system_summary(
        self,
    ) -> dict[str, Any]:

        return {
            "engine": self.executive_engine.summary(),
            "memory": self.executive_memory.summary(),
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
                    "Polecenie Executive AI jest puste."
                ),
            }

        lowered = normalized_command.lower()
        normalized_context = self._safe_dict(
            context
        )

        start_prefixes = (
            "executive ai start ",
            "executive start ",
            "ceo ai start ",
            "zarząd strategiczny start ",
            "zarzad strategiczny start ",
        )

        for prefix in start_prefixes:
            if lowered.startswith(
                prefix
            ):
                objective = normalized_command[
                    len(prefix):
                ].strip()

                return self.create_and_start(
                    objective=objective,
                    mode="SAFE_AUTONOMOUS",
                    context=normalized_context,
                )

        autonomous_prefixes = (
            "executive ai autonomous ",
            "executive autonomous ",
            "ceo ai autonomous ",
            "zarząd strategiczny autonomicznie ",
            "zarzad strategiczny autonomicznie ",
        )

        for prefix in autonomous_prefixes:
            if lowered.startswith(
                prefix
            ):
                objective = normalized_command[
                    len(prefix):
                ].strip()

                return self.create_and_start(
                    objective=objective,
                    mode="AUTONOMOUS",
                    context=normalized_context,
                    approved=True,
                )

        autodev_prefixes = (
            "executive ai autodev ",
            "executive autodev ",
            "ceo ai autodev ",
            "zarząd strategiczny autodev ",
            "zarzad strategiczny autodev ",
        )

        for prefix in autodev_prefixes:
            if lowered.startswith(
                prefix
            ):
                objective = normalized_command[
                    len(prefix):
                ].strip()

                return self._delegate_to_autodev(
                    objective=objective,
                    context=normalized_context,
                )

        create_prefixes = (
            "executive ai create ",
            "executive create ",
            "ceo ai create ",
            "zarząd strategiczny utwórz ",
            "zarzad strategiczny utworz ",
        )

        for prefix in create_prefixes:
            if lowered.startswith(
                prefix
            ):
                objective = normalized_command[
                    len(prefix):
                ].strip()

                return self.create_session(
                    objective=objective,
                    context=normalized_context,
                )

        approve_prefixes = (
            "executive ai approve ",
            "executive approve ",
            "ceo ai approve ",
            "zarząd strategiczny zaakceptuj ",
            "zarzad strategiczny zaakceptuj ",
        )

        for prefix in approve_prefixes:
            if lowered.startswith(
                prefix
            ):
                executive_id = normalized_command[
                    len(prefix):
                ].strip()

                return self.approve_session(
                    executive_id=executive_id,
                    approved=True,
                    context=normalized_context,
                )

        reject_prefixes = (
            "executive ai reject ",
            "executive reject ",
            "ceo ai reject ",
            "zarząd strategiczny odrzuć ",
            "zarzad strategiczny odrzuc ",
        )

        for prefix in reject_prefixes:
            if lowered.startswith(
                prefix
            ):
                executive_id = normalized_command[
                    len(prefix):
                ].strip()

                return self.approve_session(
                    executive_id=executive_id,
                    approved=False,
                    context=normalized_context,
                )

        status_prefixes = (
            "executive ai status ",
            "executive status ",
            "ceo ai status ",
            "zarząd strategiczny status ",
            "zarzad strategiczny status ",
        )

        for prefix in status_prefixes:
            if lowered.startswith(
                prefix
            ):
                executive_id = normalized_command[
                    len(prefix):
                ].strip()

                session = self.get_session(
                    executive_id
                )

                if session is None:
                    return {
                        "success": False,
                        "status": "NOT_FOUND",
                        "executive_id": executive_id,
                    }

                return {
                    "success": True,
                    "status": "FOUND",
                    "executive_id": executive_id,
                    "session": session,
                }

        if lowered in {
            "executive ai list",
            "executive list",
            "ceo ai list",
            "zarząd strategiczny lista",
            "zarzad strategiczny lista",
        }:
            return {
                "success": True,
                "status": "COMPLETED",
                "sessions": self.list_sessions(),
            }

        if lowered in {
            "executive ai summary",
            "executive summary",
            "ceo ai summary",
            "zarząd strategiczny podsumowanie",
            "zarzad strategiczny podsumowanie",
        }:
            return {
                "success": True,
                "status": "COMPLETED",
                "summary": self.system_summary(),
            }

        if lowered in {
            "executive ai memory",
            "executive memory",
            "ceo ai memory",
            "zarząd strategiczny pamięć",
            "zarzad strategiczny pamiec",
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
                "Nie rozpoznano polecenia Executive AI."
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
            "executive ai ",
            "executive ",
            "ceo ai ",
            "zarząd strategiczny ",
            "zarzad strategiczny ",
        )

        return normalized.startswith(
            prefixes
        )

    def _delegate_to_autodev(
        self,
        objective: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized_objective = str(
            objective
        ).strip()

        if not normalized_objective:
            return {
                "success": False,
                "status": "EMPTY_OBJECTIVE",
                "error": (
                    "Executive AI nie otrzymał "
                    "celu dla AutoDev."
                ),
            }

        controller = self.autonomous_dev_controller

        if controller is None:
            return {
                "success": False,
                "status": "AUTODEV_UNAVAILABLE",
                "error": (
                    "AutonomousDevController "
                    "nie został podłączony."
                ),
            }

        normalized_context = self._safe_dict(
            context
        )

        metadata = self._safe_dict(
            normalized_context.get(
                "metadata"
            )
        )

        metadata.update(
            {
                "source": "ExecutiveController",
                "autonomous": True,
                "safe_execution": True,
                "auto_rollback": True,
            }
        )

        normalized_context[
            "project_root"
        ] = self.project_root

        normalized_context[
            "metadata"
        ] = metadata

        handle_method = getattr(
            controller,
            "handle",
            None,
        )

        if callable(handle_method):
            try:
                result = handle_method(
                    command=normalized_objective,
                    context=normalized_context,
                )
            except TypeError:
                try:
                    result = handle_method(
                        normalized_objective,
                        normalized_context,
                    )
                except TypeError:
                    result = handle_method(
                        normalized_objective
                    )

            return self._normalize_autodev_result(
                result
            )

        execute_method = getattr(
            controller,
            "execute",
            None,
        )

        if callable(execute_method):
            payload = {
                "command": normalized_objective,
                "goal": normalized_objective,
                "context": normalized_context,
            }

            try:
                result = execute_method(
                    payload
                )
            except TypeError:
                result = execute_method(
                    normalized_objective
                )

            return self._normalize_autodev_result(
                result
            )

        return {
            "success": False,
            "status": "AUTODEV_INVALID",
            "error": (
                "AutonomousDevController nie posiada "
                "metody handle ani execute."
            ),
        }

    def _normalize_autodev_result(
        self,
        result: Any,
    ) -> dict[str, Any]:

        if isinstance(
            result,
            dict,
        ):
            return dict(
                result
            )

        to_dict = getattr(
            result,
            "to_dict",
            None,
        )

        if callable(to_dict):
            normalized = to_dict()

            if isinstance(
                normalized,
                dict,
            ):
                return normalized

        return {
            "success": True,
            "status": "COMPLETED",
            "result": result,
        }

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
