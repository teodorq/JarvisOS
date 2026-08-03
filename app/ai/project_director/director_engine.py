from __future__ import annotations

from app.core.project_paths import default_project_root

from typing import Any

from .director_execution_service import DirectorExecutionService

from app.ai.project_director.director_memory import (
    DirectorMemory,
)
from app.ai.project_director.director_planner import (
    DirectorPlanner,
)
from app.ai.project_director.director_state import (
    DirectorState,
)


_DIRECTOR_EXECUTION_SERVICE = DirectorExecutionService()


class DirectorEngine:

    def __init__(
        self,
        project_root: str | None = None,
        planner: DirectorPlanner | None = None,
        memory: DirectorMemory | None = None,
        research_service: Any | None = None,
        reasoning_service: Any | None = None,
        improvement_controller: Any | None = None,
        evolution_controller: Any | None = None,
        continuous_dev_controller: Any | None = None,
    ) -> None:

        self.project_root = str(
            project_root
            or default_project_root()
        ).strip()

        if not self.project_root:
            raise ValueError(
                "DirectorEngine wymaga project_root."
            )

        self.planner = (
            planner
            if planner is not None
            else DirectorPlanner()
        )

        self.memory = (
            memory
            if memory is not None
            else DirectorMemory()
        )

        self.research_service = research_service
        self.reasoning_service = reasoning_service
        self.improvement_controller = (
            improvement_controller
        )
        self.evolution_controller = (
            evolution_controller
        )
        self.continuous_dev_controller = (
            continuous_dev_controller
        )

        self._sessions: dict[
            str,
            DirectorState,
        ] = {}

    def create_session(
        self,
        objective: str,
        mode: str = "SAFE_AUTONOMOUS",
        max_iterations: int = 5,
        context: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        state = DirectorState(
            objective=objective,
            mode=mode,
            max_iterations=max_iterations,
            context=self._safe_dict(
                context
            ),
            metadata=self._safe_dict(
                metadata
            ),
        )

        plan = self.planner.build_plan(
            objective=objective,
            context=context,
            mode=mode,
            max_iterations=max_iterations,
        )

        state.selected_module = str(
            plan.get(
                "selected_module",
                "",
            )
        ).strip().upper()

        state.priority = str(
            plan.get(
                "priority",
                "MEDIUM",
            )
        ).strip().upper()

        state.metadata["plan_id"] = plan.get("plan_id", "")
        state.metadata["decomposition"] = self._safe_dict(
            plan.get("decomposition", {})
        )
        state.metadata["plan_steps_count"] = len(
            plan.get("steps", [])
        )

        risk = self._safe_dict(
            plan.get(
                "risk",
                {},
            )
        )

        state.risk_level = str(
            risk.get(
                "risk_level",
                "UNKNOWN",
            )
        ).strip().upper()

        state.requires_approval = bool(
            risk.get(
                "requires_approval",
                False,
            )
        )

        for step in plan.get(
            "steps",
            [],
        ):
            if not isinstance(
                step,
                dict,
            ):
                continue

            state.add_plan_step(
                name=str(
                    step.get(
                        "name",
                        "",
                    )
                ),
                module=str(
                    step.get(
                        "module",
                        "",
                    )
                ),
                description=str(
                    step.get(
                        "description",
                        "",
                    )
                ),
                priority=str(
                    step.get(
                        "priority",
                        state.priority,
                    )
                ),
            )

        state.set_status(
            "READY",
            "PLANNING_COMPLETED",
        )

        self._sessions[
            state.director_id
        ] = state

        return {
            "success": True,
            "status": state.status,
            "director_id": state.director_id,
            "state": state.to_dict(),
            "plan": plan,
        }

    def start(
        self,
        director_id: str,
        approved: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        state = self._get_state(
            director_id
        )

        if state is None:
            return {
                "success": False,
                "status": "NOT_FOUND",
                "director_id": director_id,
            }

        if state.is_terminal():
            return {
                "success": False,
                "status": state.status,
                "director_id": director_id,
                "error": (
                    "Proces Project Director jest już zakończony."
                ),
            }

        if approved is not None:
            state.set_approval(
                approved
            )

        if (
            state.requires_approval
            and state.approved is not True
        ):
            state.set_status(
                "WAITING_FOR_APPROVAL",
                "APPROVAL",
            )

            return self._build_result(
                state=state,
                success=True,
                status="WAITING_FOR_APPROVAL",
            )

        state.set_status(
            "RUNNING",
            "EXECUTION",
        )

        return self.run_iteration(
            director_id=director_id,
            context=context,
        )

    def run_iteration(self, director_id: str, context: dict[str, Any] | None=None) -> dict[str, Any]:
        return _DIRECTOR_EXECUTION_SERVICE.run_iteration(
            self,
            director_id,
            context
        )


    def approve(
        self,
        director_id: str,
        approved: bool,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        state = self._get_state(
            director_id
        )

        if state is None:
            return {
                "success": False,
                "status": "NOT_FOUND",
                "director_id": director_id,
            }

        state.set_approval(
            approved
        )

        if not approved:
            return self._finish_session(
                state=state,
                status="CANCELLED",
                module_result={
                    "success": False,
                    "status": "CANCELLED",
                    "error": (
                        "Proces odrzucony przez użytkownika."
                    ),
                },
            )

        return self.start(
            director_id=director_id,
            approved=True,
            context=context,
        )

    def get_session(
        self,
        director_id: str,
    ) -> dict[str, Any] | None:

        state = self._get_state(
            director_id
        )

        if state is None:
            return None

        return state.to_dict()

    def list_sessions(
        self,
        limit: int = 50,
    ) -> list[dict[str, Any]]:

        states = list(
            self._sessions.values()
        )

        selected = states[
            -max(
                1,
                int(
                    limit
                ),
            ):
        ]

        selected.reverse()

        return [
            state.to_dict()
            for state in selected
        ]

    def summary(
        self,
    ) -> dict[str, Any]:

        status_counts: dict[str, int] = {}

        for state in self._sessions.values():
            status_counts[
                state.status
            ] = (
                status_counts.get(
                    state.status,
                    0,
                )
                + 1
            )

        return {
            "total_sessions": len(
                self._sessions
            ),
            "status_counts": status_counts,
            "memory": self.memory.summary(),
        }

    def _execute_selected_module(self, state: DirectorState, context: dict[str, Any] | None) -> dict[str, Any]:
        return _DIRECTOR_EXECUTION_SERVICE._execute_selected_module(
            self,
            state,
            context
        )


    def _finish_session(
        self,
        state: DirectorState,
        status: str,
        module_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        state.set_status(
            status,
            "FINISHED",
        )

        result = self._build_result(
            state=state,
            success=(
                status
                in {
                    "COMPLETED",
                    "NO_ACTION",
                }
            ),
            status=status,
            module_result=module_result,
        )

        self.memory.remember(
            state=state,
            result=result,
        )

        return result

    def _build_result(
        self,
        state: DirectorState,
        success: bool,
        status: str,
        module_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return {
            "success": bool(
                success
            ),
            "status": str(
                status
            ).upper(),
            "director_id": state.director_id,
            "selected_module": state.selected_module,
            "iteration": state.iteration,
            "requires_approval": state.requires_approval,
            "approved": state.approved,
            "module_result": self._safe_dict(
                module_result
            ),
            "summary": state.summary(),
            "state": state.to_dict(),
        }

    def _get_state(
        self,
        director_id: str,
    ) -> DirectorState | None:

        return self._sessions.get(
            str(
                director_id
            ).strip()
        )

    def _normalize_result(
        self,
        result: Any,
    ) -> dict[str, Any]:

        if isinstance(
            result,
            dict,
        ):
            normalized = dict(
                result
            )

            if "success" not in normalized:
                normalized["success"] = True

            if "status" not in normalized:
                normalized["status"] = "COMPLETED"

            return normalized

        return {
            "success": True,
            "status": "COMPLETED",
            "result": result,
        }

    def _missing_module(
        self,
        module_name: str,
    ) -> dict[str, Any]:

        return {
            "success": False,
            "status": "FAILED",
            "error": (
                "Brak podłączonego modułu: "
                f"{module_name}"
            ),
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
