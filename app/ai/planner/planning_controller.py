from __future__ import annotations

from typing import Any

from app.ai.planner.long_term_planner import LongTermPlanner


class PlanningController:

    def __init__(
        self,
        planner: LongTermPlanner | None = None,
        reasoning_service: Any | None = None,
        research_service: Any | None = None,
        developer_controller: Any | None = None,
    ) -> None:

        self.planner = (
            planner
            if planner is not None
            else LongTermPlanner()
        )

        self.reasoning_service = reasoning_service
        self.research_service = research_service
        self.developer_controller = developer_controller

    def create_plan(
        self,
        title: str,
        description: str = "",
        goal_type: str = "PROJECT",
        priority: str = "MEDIUM",
        timeframe: str = "LONG_TERM",
        deadline: str | None = None,
        estimated_effort: float | None = None,
        success_criteria: list[str] | None = None,
        tags: list[str] | None = None,
        context: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized_context = self._safe_dict(
            context
        )

        reasoning_result: dict[str, Any] = {}

        if self.reasoning_service is not None:
            reasoning_result = self._run_reasoning(
                title=title,
                description=description,
                context=normalized_context,
            )

            normalized_context[
                "reasoning_result"
            ] = reasoning_result

        research_result: dict[str, Any] = {}

        if self.research_service is not None:
            research_result = self._run_research(
                title=title,
                description=description,
            )

            normalized_context[
                "research_result"
            ] = research_result

        result = self.planner.create_plan(
            title=title,
            description=description,
            goal_type=goal_type,
            priority=priority,
            timeframe=timeframe,
            deadline=deadline,
            estimated_effort=estimated_effort,
            success_criteria=(
                success_criteria or []
            ),
            tags=tags or [],
            context=normalized_context,
            metadata={
                "source": "PlanningController",
                **(metadata or {}),
            },
        )

        result["reasoning_result"] = (
            reasoning_result
        )
        result["research_result"] = (
            research_result
        )

        return result

    def build_plan(
        self,
        title: str,
        description: str = "",
        goal_type: str = "PROJECT",
        priority: str = "MEDIUM",
        timeframe: str = "LONG_TERM",
        deadline: str | None = None,
        estimated_effort: float | None = None,
        success_criteria: list[str] | None = None,
        tags: list[str] | None = None,
        context: dict[str, Any] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.create_plan(
            title=title,
            description=description,
            goal_type=goal_type,
            priority=priority,
            timeframe=timeframe,
            deadline=deadline,
            estimated_effort=estimated_effort,
            success_criteria=success_criteria,
            tags=tags,
            context=context,
            metadata=metadata,
        )

    def start_plan(
        self,
        session_id: str,
        auto_execute: bool = False,
    ) -> dict[str, Any]:

        result = self.planner.start_plan(
            session_id=session_id
        )

        if (
            not auto_execute
            or result.get(
                "success"
            ) is not True
        ):
            return result

        return self.execute_next(
            session_id=session_id
        )

    def execute_next(
        self,
        session_id: str,
    ) -> dict[str, Any]:

        next_action = self.planner.get_next_action(
            session_id=session_id
        )

        if next_action.get(
            "success"
        ) is not True:
            return next_action

        next_step = next_action.get(
            "next_step"
        )

        if not isinstance(
            next_step,
            dict,
        ):
            return {
                "success": False,
                "status": "NO_NEXT_STEP",
                "session_id": session_id,
            }

        execution_payload = {
            "session_id": session_id,
            "goal_id": next_step.get(
                "goal_id"
            ),
            "step": next_step,
        }

        if self.developer_controller is None:
            return {
                "success": True,
                "status": "READY_FOR_EXECUTION",
                "session_id": session_id,
                "payload": execution_payload,
                "message": (
                    "Plan jest gotowy, ale "
                    "DeveloperController nie został "
                    "podłączony."
                ),
            }

        try:
            developer_result = (
                self._execute_developer(
                    execution_payload
                )
            )

            success = self._detect_success(
                developer_result
            )

            if success:
                return self.planner.complete_current_goal(
                    session_id=session_id,
                    result=developer_result,
                )

            error = self._extract_error(
                developer_result
            )

            return self.planner.fail_current_goal(
                session_id=session_id,
                error=error,
                result=developer_result,
            )

        except Exception as error:
            return self.planner.fail_current_goal(
                session_id=session_id,
                error=(
                    f"PlanningController execution error: "
                    f"{type(error).__name__}: {error}"
                ),
                result={
                    "success": False,
                    "status": "FAILED",
                },
            )

    def update_progress(
        self,
        session_id: str,
        progress: float,
        current_step: str | None = None,
        actual_effort_delta: float = 0.0,
        message: str | None = None,
    ) -> dict[str, Any]:

        return self.planner.update_progress(
            session_id=session_id,
            progress=progress,
            current_step=current_step,
            actual_effort_delta=(
                actual_effort_delta
            ),
            message=message,
        )

    def complete_current_goal(
        self,
        session_id: str,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.planner.complete_current_goal(
            session_id=session_id,
            result=result,
        )

    def fail_current_goal(
        self,
        session_id: str,
        error: str,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.planner.fail_current_goal(
            session_id=session_id,
            error=error,
            result=result,
        )

    def pause_plan(
        self,
        session_id: str,
        reason: str | None = None,
    ) -> dict[str, Any]:

        return self.planner.pause_plan(
            session_id=session_id,
            reason=reason,
        )

    def resume_plan(
        self,
        session_id: str,
        auto_execute: bool = False,
    ) -> dict[str, Any]:

        result = self.planner.resume_plan(
            session_id=session_id
        )

        if (
            auto_execute
            and result.get(
                "success"
            ) is True
        ):
            return self.execute_next(
                session_id=session_id
            )

        return result

    def cancel_plan(
        self,
        session_id: str,
        reason: str | None = None,
    ) -> dict[str, Any]:

        return self.planner.cancel_plan(
            session_id=session_id,
            reason=reason,
        )

    def refresh_plan(
        self,
        session_id: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return self.planner.refresh_plan(
            session_id=session_id,
            context=context,
        )

    def get_plan(
        self,
        session_id: str,
    ) -> dict[str, Any] | None:

        return self.planner.get_session(
            session_id=session_id
        )

    def get_plan_summary(
        self,
        session_id: str,
    ) -> dict[str, Any] | None:

        return self.planner.get_session_summary(
            session_id=session_id
        )

    def get_next_action(
        self,
        session_id: str,
    ) -> dict[str, Any]:

        return self.planner.get_next_action(
            session_id=session_id
        )

    def list_plans(
        self,
        limit: int = 50,
    ) -> list[dict[str, Any]]:

        return self.planner.list_sessions(
            limit=limit
        )

    def system_summary(
        self,
    ) -> dict[str, Any]:

        return {
            "goals": self.planner.goal_summary(),
            "executions": (
                self.planner.tracker_summary()
            ),
            "memory": (
                self.planner.memory_summary()
            ),
            "sessions": self.planner.list_sessions(
                limit=100
            ),
        }

    def _run_reasoning(
        self,
        title: str,
        description: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:

        request = (
            f"{title}. {description}"
        ).strip()

        try:
            if hasattr(
                self.reasoning_service,
                "analyze",
            ):
                result = (
                    self.reasoning_service.analyze(
                        user_request=request,
                        project_context=context,
                    )
                )

            elif hasattr(
                self.reasoning_service,
                "reason",
            ):
                result = (
                    self.reasoning_service.reason(
                        user_request=request,
                        project_context=context,
                        auto_execute=False,
                    )
                )

            elif hasattr(
                self.reasoning_service,
                "handle",
            ):
                result = (
                    self.reasoning_service.handle(
                        command=(
                            "przeanalizuj bez wykonywania "
                            + request
                        ),
                        context={
                            "project_context": context,
                        },
                    )
                )

            elif callable(
                self.reasoning_service
            ):
                result = (
                    self.reasoning_service(
                        request
                    )
                )

            else:
                return {}

            return (
                dict(result)
                if isinstance(
                    result,
                    dict,
                )
                else {
                    "result": result
                }
            )

        except Exception as error:
            return {
                "success": False,
                "status": "FAILED",
                "error": (
                    f"ReasoningService error: "
                    f"{type(error).__name__}: {error}"
                ),
            }

    def _run_research(
        self,
        title: str,
        description: str,
    ) -> dict[str, Any]:

        request = (
            f"{title}. {description}"
        ).strip()

        try:
            if hasattr(
                self.research_service,
                "execute",
            ):
                result = (
                    self.research_service.execute(
                        request
                    )
                )

            elif hasattr(
                self.research_service,
                "run",
            ):
                result = (
                    self.research_service.run(
                        request
                    )
                )

            elif hasattr(
                self.research_service,
                "research",
            ):
                result = (
                    self.research_service.research(
                        request
                    )
                )

            elif callable(
                self.research_service
            ):
                result = (
                    self.research_service(
                        request
                    )
                )

            else:
                return {}

            return (
                dict(result)
                if isinstance(
                    result,
                    dict,
                )
                else {
                    "result": result
                }
            )

        except Exception as error:
            return {
                "success": False,
                "status": "FAILED",
                "error": (
                    f"ResearchService error: "
                    f"{type(error).__name__}: {error}"
                ),
            }

    def _execute_developer(
        self,
        payload: dict[str, Any],
    ) -> dict[str, Any]:

        controller = self.developer_controller

        if hasattr(
            controller,
            "execute_strategy",
        ):
            result = controller.execute_strategy(
                payload
            )

        elif hasattr(
            controller,
            "execute",
        ):
            result = controller.execute(
                payload
            )

        elif hasattr(
            controller,
            "run",
        ):
            result = controller.run(
                payload
            )

        elif hasattr(
            controller,
            "process",
        ):
            result = controller.process(
                payload
            )

        elif callable(controller):
            result = controller(
                payload
            )

        else:
            raise TypeError(
                "DeveloperController nie posiada "
                "obsługiwanej metody wykonania."
            )

        if isinstance(
            result,
            dict,
        ):
            return result

        return {
            "success": True,
            "status": "COMPLETED",
            "result": result,
        }

    def _detect_success(
        self,
        result: dict[str, Any],
    ) -> bool:

        value = result.get(
            "success"
        )

        if isinstance(
            value,
            bool,
        ):
            return value

        status = str(
            result.get(
                "status",
                "",
            )
        ).upper()

        return status in {
            "SUCCESS",
            "COMPLETED",
            "DONE",
            "VALIDATED",
        }

    def _extract_error(
        self,
        result: dict[str, Any],
    ) -> str:

        error = result.get(
            "error"
        )

        if error:
            return str(error)

        message = result.get(
            "message"
        )

        if message:
            return str(message)

        return (
            "DeveloperController zwrócił "
            "nieudany wynik."
        )

    def _safe_dict(
        self,
        value: Any,
    ) -> dict[str, Any]:

        if isinstance(
            value,
            dict,
        ):
            return dict(value)

        return {}
