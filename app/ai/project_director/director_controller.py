from __future__ import annotations

from typing import Any

from app.ai.project_director.director_engine import (
    DirectorEngine,
)
from app.ai.project_director.director_memory import (
    DirectorMemory,
)
from app.ai.project_director.director_planner import (
    DirectorPlanner,
)


class DirectorController:

    def __init__(
        self,
        project_root: str = "C:/JarvisAI",
        director_engine: DirectorEngine | None = None,
        director_memory: DirectorMemory | None = None,
        director_planner: DirectorPlanner | None = None,
        research_service: Any | None = None,
        reasoning_service: Any | None = None,
        improvement_controller: Any | None = None,
        evolution_controller: Any | None = None,
        continuous_dev_controller: Any | None = None,
        autonomous_dev_controller: Any | None = None,
        developer_controller: Any | None = None,
    ) -> None:

        self.project_root = str(
            project_root
        ).strip()

        if not self.project_root:
            raise ValueError(
                "DirectorController wymaga project_root."
            )

        self.director_memory = (
            director_memory
            if director_memory is not None
            else DirectorMemory()
        )

        self.director_planner = (
            director_planner
            if director_planner is not None
            else DirectorPlanner()
        )

        self.autonomous_dev_controller = autonomous_dev_controller
        self.developer_controller = developer_controller

        self.director_engine = (
            director_engine
            if director_engine is not None
            else DirectorEngine(
                project_root=self.project_root,
                planner=self.director_planner,
                memory=self.director_memory,
                research_service=research_service,
                reasoning_service=reasoning_service,
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

    def plan_objective(
        self,
        objective: str,
        mode: str = "SAFE_AUTONOMOUS",
        max_iterations: int = 5,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        plan = self.director_planner.build_plan(
            objective=objective,
            context=context,
            mode=mode,
            max_iterations=max_iterations,
        )

        return {
            "success": True,
            "status": "PLANNED",
            "plan": plan,
            "phases_count": len(
                plan.get("decomposition", {}).get(
                    "subgoals",
                    [],
                )
            ),
            "steps_count": len(plan.get("steps", [])),
        }

    def create_session(
        self,
        objective: str,
        mode: str = "SAFE_AUTONOMOUS",
        max_iterations: int = 5,
        context: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.director_engine.create_session(
            objective=objective,
            mode=mode,
            max_iterations=max_iterations,
            context=context,
            metadata=metadata,
        )

    def start_session(
        self,
        director_id: str,
        approved: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.director_engine.start(
            director_id=director_id,
            approved=approved,
            context=context,
        )

    def create_and_start(
        self,
        objective: str,
        mode: str = "SAFE_AUTONOMOUS",
        max_iterations: int = 5,
        context: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
        approved: bool | None = None,
    ) -> dict[str, Any]:

        created = self.create_session(
            objective=objective,
            mode=mode,
            max_iterations=max_iterations,
            context=context,
            metadata=metadata,
        )

        director_id = str(
            created.get(
                "director_id",
                "",
            )
        ).strip()

        if not director_id:
            return {
                "success": False,
                "status": "FAILED",
                "error": (
                    "DirectorController nie otrzymał "
                    "director_id."
                ),
            }

        result = self.start_session(
            director_id=director_id,
            approved=approved,
            context=context,
        )

        if mode == "AUTONOMOUS" and result.get("success", False):
            result = dict(result)

            plan_result = self.plan_objective(
                objective=objective,
                mode=mode,
                max_iterations=max_iterations,
                context=context,
            )
            plan = self._safe_dict(
                plan_result.get("plan")
            )

            result["autodev_queue"] = (
                self._enqueue_plan_in_autodev(
                    objective=objective,
                    plan=plan,
                    context=context,
                )
            )
            result["autodev"] = self._delegate_to_autodev(
                objective=objective,
                context=context,
            )

        return result

    def approve_session(
        self,
        director_id: str,
        approved: bool,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.director_engine.approve(
            director_id=director_id,
            approved=approved,
            context=context,
        )

    def get_session(
        self,
        director_id: str,
    ) -> dict[str, Any] | None:

        return self.director_engine.get_session(
            director_id
        )

    def list_sessions(
        self,
        limit: int = 50,
    ) -> list[dict[str, Any]]:

        return self.director_engine.list_sessions(
            limit=limit
        )

    def memory_summary(
        self,
    ) -> dict[str, Any]:

        return self.director_memory.summary()

    def system_summary(
        self,
    ) -> dict[str, Any]:

        return {
            "engine": self.director_engine.summary(),
            "memory": self.director_memory.summary(),
            "project_root": self.project_root,
            "autodev_available": (
                self.autonomous_dev_controller is not None
            ),
            "developer_controller_available": (
                self.developer_controller is not None
            ),
            "controller_version": "1.2.0",
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
                    "Polecenie Project Director jest puste."
                ),
            }

        lowered = normalized_command.lower()
        normalized_context = self._safe_dict(
            context
        )

        start_prefixes = (
            "project director start ",
            "director start ",
            "autonomous director start ",
            "dyrektor projektu start ",
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
            "project director autonomous ",
            "director autonomous ",
            "autonomous project director ",
            "dyrektor projektu autonomicznie ",
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

        plan_prefixes = (
            "project director plan ",
            "director plan ",
            "dyrektor projektu plan ",
            "dyrektor projektu zaplanuj ",
        )

        for prefix in plan_prefixes:
            if lowered.startswith(prefix):
                objective = normalized_command[len(prefix):].strip()

                return self.plan_objective(
                    objective=objective,
                    context=normalized_context,
                )

        create_prefixes = (
            "project director create ",
            "director create ",
            "dyrektor projektu utwórz ",
            "dyrektor projektu utworz ",
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
            "project director approve ",
            "director approve ",
            "dyrektor projektu zaakceptuj ",
        )

        for prefix in approve_prefixes:
            if lowered.startswith(
                prefix
            ):
                director_id = normalized_command[
                    len(prefix):
                ].strip()

                return self.approve_session(
                    director_id=director_id,
                    approved=True,
                    context=normalized_context,
                )

        reject_prefixes = (
            "project director reject ",
            "director reject ",
            "dyrektor projektu odrzuć ",
            "dyrektor projektu odrzuc ",
        )

        for prefix in reject_prefixes:
            if lowered.startswith(
                prefix
            ):
                director_id = normalized_command[
                    len(prefix):
                ].strip()

                return self.approve_session(
                    director_id=director_id,
                    approved=False,
                    context=normalized_context,
                )

        status_prefixes = (
            "project director status ",
            "director status ",
            "dyrektor projektu status ",
        )

        for prefix in status_prefixes:
            if lowered.startswith(
                prefix
            ):
                director_id = normalized_command[
                    len(prefix):
                ].strip()

                session = self.get_session(
                    director_id
                )

                if session is None:
                    return {
                        "success": False,
                        "status": "NOT_FOUND",
                        "director_id": director_id,
                    }

                return {
                    "success": True,
                    "status": "FOUND",
                    "director_id": director_id,
                    "session": session,
                }

        if lowered in {
            "project director list",
            "director list",
            "dyrektor projektu lista",
        }:
            return {
                "success": True,
                "status": "COMPLETED",
                "sessions": self.list_sessions(),
            }

        if lowered in {
            "project director summary",
            "director summary",
            "dyrektor projektu podsumowanie",
        }:
            return {
                "success": True,
                "status": "COMPLETED",
                "summary": self.system_summary(),
            }

        if lowered in {
            "project director memory",
            "director memory",
            "dyrektor projektu pamięć",
            "dyrektor projektu pamiec",
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
                "Nie rozpoznano polecenia Project Director."
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
            "project director ",
            "director ",
            "autonomous director ",
            "autonomous project director ",
            "dyrektor projektu ",
        )

        return normalized.startswith(
            prefixes
        )


    def _enqueue_plan_in_autodev(
        self,
        objective: str,
        plan: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        controller = self.developer_controller

        if controller is None:
            return {
                "success": False,
                "status": "DEVELOPER_CONTROLLER_UNAVAILABLE",
            }

        enqueue_plan = getattr(
            controller,
            "enqueue_director_plan",
            None,
        )

        if not callable(enqueue_plan):
            return {
                "success": False,
                "status": "DEVELOPER_CONTROLLER_INCOMPATIBLE",
            }

        try:
            result = enqueue_plan(
                objective=objective,
                plan=plan,
                context=context,
            )
        except Exception as error:
            return {
                "success": False,
                "status": "QUEUE_FAILED",
                "error": (
                    f"{type(error).__name__}: {error}"
                ),
            }

        if isinstance(result, dict):
            return result

        return {
            "success": True,
            "status": "QUEUED",
            "result": result,
        }

    def _delegate_to_autodev(
        self,
        objective: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        controller = self.autonomous_dev_controller

        if controller is None:
            return {
                "success": False,
                "status": "AUTODEV_UNAVAILABLE",
            }

        handle = getattr(controller, "handle", None)

        if callable(handle):
            try:
                result = handle(
                    command=objective,
                    context=context,
                )
            except TypeError:
                result = handle(objective)

            if isinstance(result, dict):
                return result

            return {
                "success": True,
                "status": "COMPLETED",
                "result": result,
            }

        return {
            "success": False,
            "status": "AUTODEV_INVALID",
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
