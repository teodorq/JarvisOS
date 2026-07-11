from __future__ import annotations

from typing import Any

from app.ai.executive_ai.executive_memory import (
    ExecutiveMemory,
)
from app.ai.executive_ai.executive_planner import (
    ExecutivePlanner,
)
from app.ai.executive_ai.executive_state import (
    ExecutiveState,
)


class ExecutiveEngine:

    def __init__(
        self,
        project_root: str = "C:/JarvisAI",
        planner: ExecutivePlanner | None = None,
        memory: ExecutiveMemory | None = None,
        project_director: Any | None = None,
        reasoning_service: Any | None = None,
        research_service: Any | None = None,
        improvement_controller: Any | None = None,
        evolution_controller: Any | None = None,
        continuous_dev_controller: Any | None = None,
    ) -> None:

        self.project_root = str(
            project_root
        ).strip()

        if not self.project_root:
            raise ValueError(
                "ExecutiveEngine wymaga project_root."
            )

        self.planner = (
            planner
            if planner is not None
            else ExecutivePlanner()
        )

        self.memory = (
            memory
            if memory is not None
            else ExecutiveMemory()
        )

        self.project_director = project_director
        self.reasoning_service = reasoning_service
        self.research_service = research_service
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
            ExecutiveState,
        ] = {}

    def create_session(
        self,
        objective: str,
        mode: str = "SAFE_AUTONOMOUS",
        max_phases: int = 5,
        context: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        state = ExecutiveState(
            objective=objective,
            mode=mode,
            max_phases=max_phases,
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
            max_phases=max_phases,
        )

        state.selected_strategy = str(
            plan.get(
                "selected_strategy",
                "",
            )
        ).strip().upper()

        state.delegated_module = str(
            plan.get(
                "delegated_module",
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
                module=str(
                    step.get(
                        "module",
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
            state.executive_id
        ] = state

        return {
            "success": True,
            "status": state.status,
            "executive_id": state.executive_id,
            "state": state.to_dict(),
            "plan": plan,
        }

    def start(
        self,
        executive_id: str,
        approved: bool | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        state = self._get_state(
            executive_id
        )

        if state is None:
            return {
                "success": False,
                "status": "NOT_FOUND",
                "executive_id": executive_id,
            }

        if state.is_terminal():
            return {
                "success": False,
                "status": state.status,
                "executive_id": executive_id,
                "error": (
                    "Proces Executive AI jest już zakończony."
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

        return self.run_phase(
            executive_id=executive_id,
            context=context,
        )

    def run_phase(
        self,
        executive_id: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        state = self._get_state(
            executive_id
        )

        if state is None:
            return {
                "success": False,
                "status": "NOT_FOUND",
                "executive_id": executive_id,
            }

        if not state.can_continue():
            return self._finish_session(
                state=state,
                status=(
                    state.status
                    if state.is_terminal()
                    else "COMPLETED"
                ),
            )

        try:
            state.increment_phase()

            delegated_result = self._execute_delegation(
                state=state,
                context=context,
            )

            success = bool(
                delegated_result.get(
                    "success",
                    False,
                )
            )

            status = str(
                delegated_result.get(
                    "status",
                    "UNKNOWN",
                )
            ).upper()

            state.add_result(
                source=state.delegated_module,
                status=status,
                result=delegated_result,
                success=success,
            )

            if success:
                state.add_lesson(
                    (
                        "Moduł "
                        f"{state.delegated_module} "
                        "zakończył delegację bez błędu."
                    )
                )

                if status in {
                    "WAITING_FOR_APPROVAL",
                    "WAITING",
                    "PAUSED",
                }:
                    state.set_status(
                        status,
                        "DELEGATION_WAITING",
                    )

                    return self._build_result(
                        state=state,
                        success=True,
                        status=status,
                        delegated_result=delegated_result,
                    )

                return self._finish_session(
                    state=state,
                    status="COMPLETED",
                    delegated_result=delegated_result,
                )

            error = str(
                delegated_result.get(
                    "error",
                    "Delegowany moduł zakończył operację błędem.",
                )
            )

            state.add_error(
                error
            )

            return self._finish_session(
                state=state,
                status="FAILED",
                delegated_result=delegated_result,
            )

        except Exception as exc:
            state.add_error(
                str(
                    exc
                )
            )

            return self._finish_session(
                state=state,
                status="FAILED",
                delegated_result={
                    "success": False,
                    "status": "FAILED",
                    "error": str(
                        exc
                    ),
                },
            )

    def approve(
        self,
        executive_id: str,
        approved: bool,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        state = self._get_state(
            executive_id
        )

        if state is None:
            return {
                "success": False,
                "status": "NOT_FOUND",
                "executive_id": executive_id,
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
            executive_id=executive_id,
            approved=True,
            context=context,
        )

    def get_session(
        self,
        executive_id: str,
    ) -> dict[str, Any] | None:

        state = self._get_state(
            executive_id
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

    def _execute_delegation(
        self,
        state: ExecutiveState,
        context: dict[str, Any] | None,
    ) -> dict[str, Any]:

        module = state.delegated_module
        command = state.objective

        execution_context = {
            "project_root": self.project_root,
            "executive_id": state.executive_id,
            "phase": state.phase,
            "metadata": {
                "source": "ExecutiveEngine",
            },
            **self._safe_dict(
                context
            ),
        }

        if module == ExecutivePlanner.MODULE_PROJECT_DIRECTOR:
            if self.project_director is None:
                return self._missing_module(
                    module
                )

            director_command = command

            if not command.lower().startswith(
                (
                    "project director ",
                    "director ",
                    "autonomous project director ",
                    "dyrektor projektu ",
                )
            ):
                director_command = (
                    "project director start "
                    + command
                )

            return self._normalize_result(
                self.project_director.handle(
                    command=director_command,
                    context=execution_context,
                )
            )

        if module == ExecutivePlanner.MODULE_REASONER:
            if self.reasoning_service is None:
                return self._missing_module(
                    module
                )

            return self._normalize_result(
                self.reasoning_service.handle(
                    command=command,
                    context=execution_context,
                )
            )

        if module == ExecutivePlanner.MODULE_RESEARCH:
            if self.research_service is None:
                return self._missing_module(
                    module
                )

            return self._normalize_result(
                self.research_service.execute(
                    command
                )
            )

        if module == ExecutivePlanner.MODULE_SELF_IMPROVEMENT:
            if self.improvement_controller is None:
                return self._missing_module(
                    module
                )

            improvement_command = command

            if not command.lower().startswith(
                (
                    "self improvement ",
                    "improvement brain ",
                    "samodoskonalenie ",
                )
            ):
                improvement_command = (
                    "self improvement analyze "
                    + command
                )

            return self._normalize_result(
                self.improvement_controller.handle(
                    command=improvement_command,
                    context=execution_context,
                )
            )

        if module == ExecutivePlanner.MODULE_EVOLUTION:
            if self.evolution_controller is None:
                return self._missing_module(
                    module
                )

            evolution_command = command

            if not command.lower().startswith(
                (
                    "evolution ",
                    "auto evolution ",
                    "ewolucja ",
                )
            ):
                evolution_command = (
                    "evolution start "
                    + command
                )

            return self._normalize_result(
                self.evolution_controller.handle(
                    command=evolution_command,
                    context=execution_context,
                )
            )

        if module == ExecutivePlanner.MODULE_CONTINUOUS_DEV:
            if self.continuous_dev_controller is None:
                return self._missing_module(
                    module
                )

            return self._normalize_result(
                self.continuous_dev_controller.handle(
                    command=command,
                    context=execution_context,
                )
            )

        return {
            "success": False,
            "status": "NO_ACTION",
            "error": (
                "Executive AI nie wybrał obsługiwanego modułu."
            ),
        }

    def _finish_session(
        self,
        state: ExecutiveState,
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
        state: ExecutiveState,
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
            "executive_id": state.executive_id,
            "selected_strategy": state.selected_strategy,
            "delegated_module": state.delegated_module,
            "phase": state.phase,
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
        executive_id: str,
    ) -> ExecutiveState | None:

        return self._sessions.get(
            str(
                executive_id
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
