from __future__ import annotations

from app.core.project_paths import default_project_root

from typing import Any

from .meta_execution_service import MetaExecutionService

from app.ai.meta_executive.meta_memory import (
    MetaMemory,
)
from app.ai.meta_executive.meta_planner import (
    MetaPlanner,
)
from app.ai.meta_executive.meta_state import (
    MetaState,
)


_META_EXECUTION_SERVICE = MetaExecutionService()


class MetaEngine:

    def __init__(
        self,
        project_root: str | None = None,
        planner: MetaPlanner | None = None,
        memory: MetaMemory | None = None,
        executive_controller: Any | None = None,
        project_director: Any | None = None,
        improvement_controller: Any | None = None,
        evolution_controller: Any | None = None,
        continuous_dev_controller: Any | None = None,
        reasoning_service: Any | None = None,
        research_service: Any | None = None,
    ) -> None:

        self.project_root = str(
            project_root
            or default_project_root()
        ).strip()

        if not self.project_root:
            raise ValueError(
                "MetaEngine wymaga project_root."
            )

        self.planner = (
            planner
            if planner is not None
            else MetaPlanner()
        )

        self.memory = (
            memory
            if memory is not None
            else MetaMemory()
        )

        self.executive_controller = (
            executive_controller
        )
        self.project_director = (
            project_director
        )
        self.improvement_controller = (
            improvement_controller
        )
        self.evolution_controller = (
            evolution_controller
        )
        self.continuous_dev_controller = (
            continuous_dev_controller
        )
        self.reasoning_service = reasoning_service
        self.research_service = research_service

        self._sessions: dict[
            str,
            MetaState,
        ] = {}

    def create_session(
        self,
        objective: str,
        mode: str = "SAFE_AUTONOMOUS",
        max_cycles: int = 5,
        context: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        state = MetaState(
            objective=objective,
            mode=mode,
            max_cycles=max_cycles,
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
            max_cycles=max_cycles,
        )

        state.selected_strategy = str(
            plan.get(
                "selected_strategy",
                "",
            )
        ).strip().upper()

        state.selected_layer = str(
            plan.get(
                "selected_layer",
                "",
            )
        ).strip().upper()

        state.priority = str(
            plan.get(
                "priority",
                "MEDIUM",
            )
        ).strip().upper()

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
            "roadmap",
            [],
        ):
            if not isinstance(
                step,
                dict,
            ):
                continue

            state.add_roadmap_step(
                name=str(
                    step.get(
                        "name",
                        "",
                    )
                ),
                description=str(
                    step.get(
                        "description",
                        "",
                    )
                ),
                layer=str(
                    step.get(
                        "layer",
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
            state.meta_id
        ] = state

        return {
            "success": True,
            "status": state.status,
            "meta_id": state.meta_id,
            "state": state.to_dict(),
            "plan": plan,
        }

    def start(
        self,
        meta_id: str,
        approved: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        state = self._get_state(
            meta_id
        )

        if state is None:
            return {
                "success": False,
                "status": "NOT_FOUND",
                "meta_id": meta_id,
            }

        if state.is_terminal():
            return {
                "success": False,
                "status": state.status,
                "meta_id": meta_id,
                "error": (
                    "Proces Meta Executive jest już zakończony."
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
            "DELEGATION",
        )

        return self.run_cycle(
            meta_id=meta_id,
            context=context,
        )

    def run_cycle(self, meta_id: str, context: dict[str, Any] | None=None) -> dict[str, Any]:
        return _META_EXECUTION_SERVICE.run_cycle(
            self,
            meta_id,
            context
        )


    def approve(
        self,
        meta_id: str,
        approved: bool,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        state = self._get_state(
            meta_id
        )

        if state is None:
            return {
                "success": False,
                "status": "NOT_FOUND",
                "meta_id": meta_id,
            }

        state.set_approval(
            approved
        )

        if not approved:
            return self._finish_session(
                state=state,
                status="CANCELLED",
                delegated_result={
                    "success": False,
                    "status": "CANCELLED",
                    "error": (
                        "Proces odrzucony przez użytkownika."
                    ),
                },
            )

        return self.start(
            meta_id=meta_id,
            approved=True,
            context=context,
        )

    def get_session(
        self,
        meta_id: str,
    ) -> dict[str, Any] | None:

        state = self._get_state(
            meta_id
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

    def _execute_selected_layer(self, state: MetaState, context: dict[str, Any] | None) -> dict[str, Any]:
        return _META_EXECUTION_SERVICE._execute_selected_layer(
            self,
            state,
            context
        )


    def _finish_session(
        self,
        state: MetaState,
        status: str,
        delegated_result: dict[str, Any] | None = None,
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
            delegated_result=delegated_result,
        )

        self.memory.remember(
            state=state,
            result=result,
        )

        return result

    def _build_result(
        self,
        state: MetaState,
        success: bool,
        status: str,
        delegated_result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return {
            "success": bool(
                success
            ),
            "status": str(
                status
            ).upper(),
            "meta_id": state.meta_id,
            "selected_strategy": state.selected_strategy,
            "selected_layer": state.selected_layer,
            "cycle": state.cycle,
            "requires_approval": state.requires_approval,
            "approved": state.approved,
            "delegated_result": self._safe_dict(
                delegated_result
            ),
            "summary": state.summary(),
            "state": state.to_dict(),
        }

    def _get_state(
        self,
        meta_id: str,
    ) -> MetaState | None:

        return self._sessions.get(
            str(
                meta_id
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

    def _missing_layer(
        self,
        layer_name: str,
    ) -> dict[str, Any]:

        return {
            "success": False,
            "status": "FAILED",
            "error": (
                "Brak podłączonej warstwy: "
                f"{layer_name}"
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
