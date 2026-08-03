from __future__ import annotations

from .evolution_command_router import EvolutionCommandRouter

from app.core.project_paths import default_project_root

from typing import Any

from app.ai.evolution.evolution_engine import (
    EvolutionEngine,
)
from app.ai.evolution.evolution_memory import (
    EvolutionMemory,
)
from app.ai.evolution.evolution_planner import (
    EvolutionPlanner,
)


_EVOLUTION_COMMAND_ROUTER = EvolutionCommandRouter()


class EvolutionController:

    def __init__(
        self,
        project_root: str | None = None,
        evolution_engine: EvolutionEngine | None = None,
        evolution_memory: EvolutionMemory | None = None,
        evolution_planner: EvolutionPlanner | None = None,
        autonomous_dev_controller: Any | None = None,
    ) -> None:

        self.project_root = str(
            project_root
            or default_project_root()
        ).strip()

        if not self.project_root:
            raise ValueError(
                "EvolutionController wymaga project_root."
            )

        self.autonomous_dev_controller = (
            autonomous_dev_controller
        )

        self.evolution_engine = (
            evolution_engine
            if evolution_engine is not None
            else EvolutionEngine(
                project_root=self.project_root
            )
        )

        self.evolution_memory = (
            evolution_memory
            if evolution_memory is not None
            else EvolutionMemory()
        )

        self.evolution_planner = (
            evolution_planner
            if evolution_planner is not None
            else EvolutionPlanner()
        )

    def create_run(
        self,
        objective: str,
        mode: str = "SAFE_AUTONOMOUS",
        max_iterations: int = 5,
        context: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized_context = self._safe_dict(
            context
        )

        plan = self.evolution_planner.build(
            objective=objective,
            mode=mode,
            iterations=max_iterations,
            context=normalized_context,
        )

        created = self.evolution_engine.create_run(
            objective=objective,
            mode=mode,
            max_iterations=max_iterations,
            metadata={
                "source": "EvolutionController",
                "plan_id": plan.get(
                    "plan_id"
                ),
                **(metadata or {}),
            },
        )

        created["plan"] = plan
        return created

    def start_run(
        self,
        evolution_id: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        result = self.evolution_engine.start(
            evolution_id=evolution_id,
            context=context,
        )

        self._remember_if_terminal(
            evolution_id=evolution_id,
            result=result,
        )

        return result

    def create_and_start(
        self,
        objective: str,
        mode: str = "SAFE_AUTONOMOUS",
        max_iterations: int = 5,
        context: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        created = self.create_run(
            objective=objective,
            mode=mode,
            max_iterations=max_iterations,
            context=context,
            metadata=metadata,
        )

        evolution_id = str(
            created.get(
                "evolution_id",
                "",
            )
        ).strip()

        if not evolution_id:
            return {
                "success": False,
                "status": "FAILED",
                "error": (
                    "EvolutionController nie otrzymał "
                    "evolution_id."
                ),
            }

        result = self.start_run(
            evolution_id=evolution_id,
            context=context,
        )

        result["plan"] = created.get(
            "plan",
            {},
        )

        if (
            mode == "AUTONOMOUS"
            and result.get("success", False)
        ):
            result["autodev"] = self._delegate_to_autodev(
                objective=objective,
                context=context,
            )

        return result

    def run_iteration(
        self,
        evolution_id: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        result = self.evolution_engine.run_iteration(
            evolution_id=evolution_id,
            context=context,
        )

        self._remember_if_terminal(
            evolution_id=evolution_id,
            result=result,
        )

        return result

    def continue_run(
        self,
        evolution_id: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        result = self.evolution_engine.continue_run(
            evolution_id=evolution_id,
            context=context,
        )

        self._remember_if_terminal(
            evolution_id=evolution_id,
            result=result,
        )

        return result

    def approve_run(
        self,
        evolution_id: str,
        approved: bool,
        note: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        result = self.evolution_engine.approve(
            evolution_id=evolution_id,
            approved=approved,
            note=note,
            context=context,
        )

        self._remember_if_terminal(
            evolution_id=evolution_id,
            result=result,
        )

        return result

    def pause_run(
        self,
        evolution_id: str,
        reason: str | None = None,
    ) -> dict[str, Any]:

        return self.evolution_engine.pause(
            evolution_id=evolution_id,
            reason=reason,
        )

    def resume_run(
        self,
        evolution_id: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        result = self.evolution_engine.resume(
            evolution_id=evolution_id,
            context=context,
        )

        self._remember_if_terminal(
            evolution_id=evolution_id,
            result=result,
        )

        return result

    def cancel_run(
        self,
        evolution_id: str,
        reason: str | None = None,
    ) -> dict[str, Any]:

        result = self.evolution_engine.cancel(
            evolution_id=evolution_id,
            reason=reason,
        )

        self._remember_if_terminal(
            evolution_id=evolution_id,
            result=result,
        )

        return result

    def get_run(
        self,
        evolution_id: str,
    ) -> dict[str, Any] | None:

        return self.evolution_engine.get_run(
            evolution_id=evolution_id
        )

    def list_runs(
        self,
        limit: int = 50,
    ) -> list[dict[str, Any]]:

        return self.evolution_engine.list_runs(
            limit=limit
        )

    def memory_summary(
        self,
    ) -> dict[str, Any]:

        return self.evolution_memory.summary()

    def system_summary(
        self,
    ) -> dict[str, Any]:

        return {
            "engine": self.evolution_engine.summary(),
            "memory": self.evolution_memory.summary(),
            "runs": self.evolution_engine.list_runs(
                limit=100
            ),
        }

    def handle(
        self,
        command: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return _EVOLUTION_COMMAND_ROUTER.handle(
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
            "evolution ",
            "auto evolution ",
            "ewolucja ",
            "uruchom ewolucję ",
            "uruchom ewolucje ",
        )

        return normalized.startswith(
            prefixes
        )

    def _remember_if_terminal(
        self,
        evolution_id: str,
        result: dict[str, Any],
    ) -> None:

        status = str(
            result.get(
                "status",
                "",
            )
        ).upper()

        terminal_statuses = {
            "COMPLETED",
            "NO_CHANGES",
            "FAILED",
            "CANCELLED",
        }

        if status not in terminal_statuses:
            return

        run = self.evolution_engine.get_run(
            evolution_id
        )

        if run is None:
            return

        existing = self.evolution_memory.get(
            evolution_id
        )

        if existing is None:
            self.evolution_memory.remember(
                evolution_run=run,
                result=result,
            )

        else:
            self.evolution_memory.update(
                evolution_id=evolution_id,
                status=status,
                decision=result.get(
                    "decision"
                ),
                iteration=result.get(
                    "iteration"
                ),
                result=result,
                lessons=self._safe_list(
                    result.get(
                        "lessons",
                        [],
                    )
                ),
                errors=self._safe_list(
                    result.get(
                        "errors",
                        [],
                    )
                ),
                warnings=self._safe_list(
                    result.get(
                        "warnings",
                        [],
                    )
                ),
            )

    def _delegate_to_autodev(
        self,
        objective:str,
        context:dict[str,Any]|None=None,
    )->dict[str,Any]:

        controller=self.autonomous_dev_controller

        if controller is None:
            return {
                "success":False,
                "status":"AUTODEV_UNAVAILABLE",
            }

        handle=getattr(controller,"handle",None)

        if callable(handle):
            try:
                result=handle(
                    command=objective,
                    context=context,
                )
            except TypeError:
                result=handle(objective)

            if isinstance(result,dict):
                return result

            return {
                "success":True,
                "status":"COMPLETED",
                "result":result,
            }

        return {
            "success":False,
            "status":"AUTODEV_INVALID",
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
