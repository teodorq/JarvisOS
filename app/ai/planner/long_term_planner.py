"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations

from typing import Any

from app.ai.planner.execution_tracker import ExecutionTracker
from app.ai.planner.goal_decomposer import GoalDecomposer
from app.ai.planner.goal_graph import GoalGraph
from app.ai.planner.goal_manager import GoalManager
from app.ai.planner.goal_scheduler import GoalScheduler
from app.ai.planner.planning_memory import PlanningMemory
from app.ai.planner.planning_session import PlanningSession
from app.ai.planner.priority_manager import PriorityManager


class LongTermPlanner:

    def __init__(
        self,
        goal_manager: GoalManager | None = None,
        goal_graph: GoalGraph | None = None,
        goal_decomposer: GoalDecomposer | None = None,
        priority_manager: PriorityManager | None = None,
        goal_scheduler: GoalScheduler | None = None,
        execution_tracker: ExecutionTracker | None = None,
        planning_memory: PlanningMemory | None = None,
    ) -> None:

        self.goal_manager = (
            goal_manager
            if goal_manager is not None
            else GoalManager()
        )

        self.goal_graph = (
            goal_graph
            if goal_graph is not None
            else GoalGraph()
        )

        self.goal_decomposer = (
            goal_decomposer
            if goal_decomposer is not None
            else GoalDecomposer()
        )

        self.priority_manager = (
            priority_manager
            if priority_manager is not None
            else PriorityManager()
        )

        self.goal_scheduler = (
            goal_scheduler
            if goal_scheduler is not None
            else GoalScheduler()
        )

        self.execution_tracker = (
            execution_tracker
            if execution_tracker is not None
            else ExecutionTracker()
        )

        self.planning_memory = (
            planning_memory
            if planning_memory is not None
            else PlanningMemory()
        )

        self._sessions: dict[
            str,
            PlanningSession,
        ] = {}

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

        root_goal = self.goal_manager.create_goal(
            title=title,
            description=description,
            goal_type=goal_type,
            priority=priority,
            timeframe=timeframe,
            deadline=deadline,
            estimated_effort=estimated_effort,
            success_criteria=success_criteria or [],
            tags=tags or [],
            metadata={
                "source": "LongTermPlanner",
                **(metadata or {}),
            },
        )

        session = PlanningSession(
            root_goal_id=root_goal["goal_id"],
            title=root_goal["title"],
            metadata={
                "planner_version": "1.0.0",
                **(metadata or {}),
            },
        )

        self._sessions[
            session.session_id
        ] = session

        session.start_building()
        session.set_goal(root_goal)

        decomposition = (
            self.goal_decomposer.decompose(
                goal=root_goal,
                context=normalized_context,
            )
        )

        session.set_decomposition(
            decomposition
        )

        created_subgoals = self._create_subgoals(
            root_goal=root_goal,
            decomposition=decomposition,
        )

        goals = [
            root_goal,
            *created_subgoals,
        ]

        graph = self.goal_graph.build(
            goals
        )

        session.set_graph(
            graph
        )

        priority_result = (
            self.priority_manager.evaluate(
                goals=goals,
                context=normalized_context,
            )
        )

        session.set_priority_result(
            priority_result
        )

        schedule = self.goal_scheduler.schedule(
            goals=goals,
            priority_result=priority_result,
            graph_result=graph,
            context=normalized_context,
        )

        session.set_schedule(
            schedule
        )

        result = {
            "success": True,
            "status": session.status,
            "session_id": session.session_id,
            "root_goal": root_goal,
            "subgoals": created_subgoals,
            "decomposition": decomposition,
            "graph": graph,
            "priority_result": priority_result,
            "schedule": schedule,
            "next_goal_id": schedule.get(
                "next_goal_id"
            ),
            "summary": session.summary(),
        }

        session.result = dict(result)

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
    ) -> dict[str, Any]:

        session = self._get_session(
            session_id
        )

        if session is None:
            return self._not_found(
                session_id
            )

        next_goal_id = session.next_goal_id

        if not next_goal_id:
            next_step = session.next_ready_step()

            if next_step is not None:
                next_goal_id = next_step.get(
                    "goal_id"
                )

        if not next_goal_id:
            return {
                "success": False,
                "status": "BLOCKED",
                "session_id": session_id,
                "error": (
                    "Brak celu gotowego "
                    "do wykonania."
                ),
                "summary": session.summary(),
            }

        goal = self.goal_manager.get_goal(
            next_goal_id
        )

        if goal is None:
            step = self._find_session_step_by_goal(
                session,
                next_goal_id,
            )

            if step is not None:
                goal = {
                    "goal_id": next_goal_id,
                    "title": step.get(
                        "name",
                        next_goal_id,
                    ),
                    "estimated_effort": (
                        self._safe_dict(
                            step.get(
                                "metadata",
                                {},
                            )
                        ).get(
                            "estimated_effort"
                        )
                    ),
                }

        if goal is None:
            return {
                "success": False,
                "status": "NOT_FOUND",
                "session_id": session_id,
                "error": (
                    "Nie znaleziono następnego celu."
                ),
            }

        execution = self.execution_tracker.create(
            goal_id=goal["goal_id"],
            title=goal["title"],
            estimated_effort=goal.get(
                "estimated_effort"
            ),
            metadata={
                "planning_session_id": (
                    session_id
                ),
            },
        )

        execution = self.execution_tracker.start(
            execution_id=execution[
                "execution_id"
            ],
        )

        if execution is None:
            return {
                "success": False,
                "status": "FAILED",
                "session_id": session_id,
                "error": (
                    "Nie udało się uruchomić "
                    "ExecutionTracker."
                ),
            }

        session.start()
        session.set_execution(
            execution
        )

        step = self._find_session_step_by_goal(
            session,
            goal["goal_id"],
        )

        if step is not None:
            session.start_step(
                step["step_id"]
            )

        self.goal_manager.activate_goal(
            goal["goal_id"]
        )

        return {
            "success": True,
            "status": session.status,
            "session_id": session_id,
            "execution": execution,
            "goal": goal,
            "summary": session.summary(),
        }

    def update_progress(
        self,
        session_id: str,
        progress: float,
        current_step: str | None = None,
        actual_effort_delta: float = 0.0,
        message: str | None = None,
    ) -> dict[str, Any]:

        session = self._get_session(
            session_id
        )

        if session is None:
            return self._not_found(
                session_id
            )

        execution_id = self._current_execution_id(
            session
        )

        if execution_id is None:
            return {
                "success": False,
                "status": "NO_EXECUTION",
                "session_id": session_id,
            }

        execution = (
            self.execution_tracker.update_progress(
                execution_id=execution_id,
                progress=progress,
                current_step=current_step,
                actual_effort_delta=(
                    actual_effort_delta
                ),
                message=message,
            )
        )

        if execution is None:
            return {
                "success": False,
                "status": "NOT_FOUND",
                "session_id": session_id,
                "execution_id": execution_id,
            }

        session.set_execution(
            execution
        )

        if session.current_step_id:
            session.update_step_progress(
                step_id=session.current_step_id,
                progress=progress,
                output={
                    "message": message,
                    "execution_id": (
                        execution_id
                    ),
                },
            )

        goal_id = execution.get(
            "goal_id"
        )

        if goal_id:
            self.goal_manager.set_progress(
                goal_id=goal_id,
                progress=progress,
            )

        if execution.get(
            "status"
        ) == "COMPLETED":
            return self.complete_current_goal(
                session_id=session_id,
                result=execution.get(
                    "result",
                    {},
                ),
            )

        return {
            "success": True,
            "status": session.status,
            "session_id": session_id,
            "execution": execution,
            "summary": session.summary(),
        }

    def complete_current_goal(
        self,
        session_id: str,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        session = self._get_session(
            session_id
        )

        if session is None:
            return self._not_found(
                session_id
            )

        execution_id = self._current_execution_id(
            session
        )

        if execution_id is None:
            return {
                "success": False,
                "status": "NO_EXECUTION",
                "session_id": session_id,
            }

        execution = self.execution_tracker.complete(
            execution_id=execution_id,
            result=result,
        )

        if execution is None:
            return {
                "success": False,
                "status": "NOT_FOUND",
                "session_id": session_id,
                "execution_id": execution_id,
            }

        goal_id = execution["goal_id"]

        self.goal_manager.complete_goal(
            goal_id
        )

        if session.current_step_id:
            session.complete_step(
                step_id=session.current_step_id,
                output=(
                    result
                    if isinstance(
                        result,
                        dict,
                    )
                    else {}
                ),
            )

        session.set_execution(
            execution
        )

        self._refresh_session_plan(
            session
        )

        if self._session_is_complete(
            session
        ):
            final_result = {
                "success": True,
                "status": "COMPLETED",
                "session_id": session_id,
            }

            session.complete(
                result=final_result
            )

            self.planning_memory.remember(
                session=session.to_dict(),
                result=final_result,
            )

            return {
                **final_result,
                "summary": session.summary(),
            }

        return {
            "success": True,
            "status": session.status,
            "session_id": session_id,
            "completed_goal_id": goal_id,
            "next_goal_id": session.next_goal_id,
            "schedule": session.schedule,
            "summary": session.summary(),
        }

    def fail_current_goal(
        self,
        session_id: str,
        error: str,
        result: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        session = self._get_session(
            session_id
        )

        if session is None:
            return self._not_found(
                session_id
            )

        execution_id = self._current_execution_id(
            session
        )

        if execution_id is None:
            return {
                "success": False,
                "status": "NO_EXECUTION",
                "session_id": session_id,
            }

        execution = self.execution_tracker.fail(
            execution_id=execution_id,
            error=error,
            result=result,
        )

        if execution is None:
            return {
                "success": False,
                "status": "NOT_FOUND",
                "session_id": session_id,
            }

        goal_id = execution["goal_id"]

        self.goal_manager.fail_goal(
            goal_id=goal_id,
            reason=error,
        )

        if session.current_step_id:
            session.fail_step(
                step_id=session.current_step_id,
                error=error,
                output=result,
            )

        session.set_execution(
            execution
        )

        failed_result = {
            "success": False,
            "status": "FAILED",
            "session_id": session_id,
            "goal_id": goal_id,
            "error": error,
        }

        session.fail(
            error=error,
            result=failed_result,
        )

        self.planning_memory.remember(
            session=session.to_dict(),
            result=failed_result,
        )

        return {
            **failed_result,
            "summary": session.summary(),
        }

    def pause_plan(
        self,
        session_id: str,
        reason: str | None = None,
    ) -> dict[str, Any]:

        session = self._get_session(
            session_id
        )

        if session is None:
            return self._not_found(
                session_id
            )

        execution_id = self._current_execution_id(
            session
        )

        if execution_id:
            execution = self.execution_tracker.pause(
                execution_id=execution_id,
                reason=reason,
            )

            if execution is not None:
                session.set_execution(
                    execution
                )

        session.pause(
            reason=reason
        )

        return {
            "success": True,
            "status": session.status,
            "session_id": session_id,
            "summary": session.summary(),
        }

    def resume_plan(
        self,
        session_id: str,
    ) -> dict[str, Any]:

        session = self._get_session(
            session_id
        )

        if session is None:
            return self._not_found(
                session_id
            )

        execution_id = self._current_execution_id(
            session
        )

        if execution_id:
            execution = self.execution_tracker.resume(
                execution_id
            )

            if execution is not None:
                session.set_execution(
                    execution
                )

        session.resume()

        return {
            "success": True,
            "status": session.status,
            "session_id": session_id,
            "summary": session.summary(),
        }

    def cancel_plan(
        self,
        session_id: str,
        reason: str | None = None,
    ) -> dict[str, Any]:

        session = self._get_session(
            session_id
        )

        if session is None:
            return self._not_found(
                session_id
            )

        execution_id = self._current_execution_id(
            session
        )

        if execution_id:
            self.execution_tracker.cancel(
                execution_id=execution_id,
                reason=reason,
            )

        session.cancel(
            reason=reason
        )

        self.goal_manager.cancel_goal(
            goal_id=session.root_goal_id,
            reason=reason,
        )

        result = {
            "success": False,
            "status": "CANCELLED",
            "session_id": session_id,
            "reason": reason,
        }

        self.planning_memory.remember(
            session=session.to_dict(),
            result=result,
        )

        return {
            **result,
            "summary": session.summary(),
        }

    def get_session(
        self,
        session_id: str,
    ) -> dict[str, Any] | None:

        session = self._get_session(
            session_id
        )

        if session is None:
            return None

        return session.to_dict()

    def get_session_summary(
        self,
        session_id: str,
    ) -> dict[str, Any] | None:

        session = self._get_session(
            session_id
        )

        if session is None:
            return None

        return session.summary()

    def list_sessions(
        self,
        limit: int = 50,
    ) -> list[dict[str, Any]]:

        sessions = list(
            self._sessions.values()
        )

        sessions.sort(
            key=lambda item: item.updated_at,
            reverse=True,
        )

        return [
            session.summary()
            for session in sessions[
                :max(
                    1,
                    int(limit),
                )
            ]
        ]

    def get_next_action(
        self,
        session_id: str,
    ) -> dict[str, Any]:

        session = self._get_session(
            session_id
        )

        if session is None:
            return self._not_found(
                session_id
            )

        next_step = session.next_ready_step()

        return {
            "success": True,
            "status": session.status,
            "session_id": session_id,
            "next_goal_id": session.next_goal_id,
            "next_step": next_step,
            "schedule": session.schedule,
        }

    def refresh_plan(
        self,
        session_id: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        session = self._get_session(
            session_id
        )

        if session is None:
            return self._not_found(
                session_id
            )

        self._refresh_session_plan(
            session,
            context=context,
        )

        return {
            "success": True,
            "status": session.status,
            "session_id": session_id,
            "graph": session.graph,
            "priority_result": (
                session.priority_result
            ),
            "schedule": session.schedule,
            "summary": session.summary(),
        }

    def memory_summary(
        self,
    ) -> dict[str, Any]:

        return self.planning_memory.summary()

    def tracker_summary(
        self,
    ) -> dict[str, Any]:

        return self.execution_tracker.summary()

    def goal_summary(
        self,
    ) -> dict[str, Any]:

        return self.goal_manager.summary()

    def _create_subgoals(
        self,
        root_goal: dict[str, Any],
        decomposition: dict[str, Any],
    ) -> list[dict[str, Any]]:

        proposals = decomposition.get(
            "subgoals",
            [],
        )

        if not isinstance(
            proposals,
            list,
        ):
            return []

        proposal_to_goal: dict[
            str,
            str,
        ] = {}

        created: list[
            dict[str, Any]
        ] = []

        for proposal in proposals:
            if not isinstance(
                proposal,
                dict,
            ):
                continue

            child = self.goal_manager.create_goal(
                title=str(
                    proposal.get(
                        "title",
                        "Nieznany podcel",
                    )
                ),
                description=str(
                    proposal.get(
                        "description",
                        "",
                    )
                ),
                goal_type=self._map_subgoal_type(
                    proposal.get(
                        "subgoal_type"
                    )
                ),
                priority=str(
                    proposal.get(
                        "priority",
                        root_goal.get(
                            "priority",
                            "MEDIUM",
                        ),
                    )
                ),
                timeframe=root_goal.get(
                    "timeframe",
                    "LONG_TERM",
                ),
                parent_goal_id=root_goal[
                    "goal_id"
                ],
                tags=self._safe_string_list(
                    proposal.get(
                        "tags",
                        [],
                    )
                ),
                success_criteria=self._safe_string_list(
                    proposal.get(
                        "success_criteria",
                        [],
                    )
                ),
                estimated_effort=proposal.get(
                    "estimated_effort"
                ),
                metadata={
                    "proposal_id": proposal.get(
                        "proposal_id"
                    ),
                    "subgoal_type": proposal.get(
                        "subgoal_type"
                    ),
                    "source": "GoalDecomposer",
                },
            )

            proposal_id = str(
                proposal.get(
                    "proposal_id",
                    "",
                )
            )

            if proposal_id:
                proposal_to_goal[
                    proposal_id
                ] = child["goal_id"]

            created.append(child)

        for proposal, child in zip(
            [
                item
                for item in proposals
                if isinstance(item, dict)
            ],
            created,
        ):
            dependencies = self._safe_string_list(
                proposal.get(
                    "dependencies",
                    [],
                )
            )

            for proposal_dependency_id in dependencies:
                dependency_goal_id = (
                    proposal_to_goal.get(
                        proposal_dependency_id
                    )
                )

                if dependency_goal_id:
                    self.goal_manager.add_dependency(
                        goal_id=child[
                            "goal_id"
                        ],
                        dependency_goal_id=(
                            dependency_goal_id
                        ),
                    )

        return [
            self.goal_manager.get_goal(
                item["goal_id"]
            )
            for item in created
            if self.goal_manager.get_goal(
                item["goal_id"]
            )
            is not None
        ]

    def _refresh_session_plan(
        self,
        session: PlanningSession,
        context: dict[str, Any] | None = None,
    ) -> None:

        goals = [
            goal
            for goal in self.goal_manager.list_goals()
            if (
                goal["goal_id"]
                == session.root_goal_id
                or goal.get(
                    "parent_goal_id"
                )
                == session.root_goal_id
            )
        ]

        graph = self.goal_graph.build(
            goals
        )

        priority_result = (
            self.priority_manager.evaluate(
                goals=goals,
                context=self._safe_dict(
                    context
                ),
            )
        )

        schedule = self.goal_scheduler.schedule(
            goals=goals,
            priority_result=priority_result,
            graph_result=graph,
            context=self._safe_dict(
                context
            ),
        )

        session.set_graph(
            graph
        )

        session.set_priority_result(
            priority_result
        )

        session.set_schedule(
            schedule
        )

    def _session_is_complete(
        self,
        session: PlanningSession,
    ) -> bool:

        children = self.goal_manager.get_children(
            session.root_goal_id
        )

        if not children:
            root = self.goal_manager.get_goal(
                session.root_goal_id
            )

            return bool(
                root
                and root.get(
                    "status"
                ) == "COMPLETED"
            )

        return all(
            child.get(
                "status"
            ) == "COMPLETED"
            for child in children
        )

    def _current_execution_id(
        self,
        session: PlanningSession,
    ) -> str | None:

        return self._optional_string(
            session.execution.get(
                "execution_id"
            )
        )

    def _find_session_step_by_goal(
        self,
        session: PlanningSession,
        goal_id: str,
    ) -> dict[str, Any] | None:

        for step in session.get_steps():
            if step.get(
                "goal_id"
            ) == goal_id:
                return step

        return None

    def _map_subgoal_type(
        self,
        subgoal_type: Any,
    ) -> str:

        normalized = str(
            subgoal_type
        ).upper()

        mapping = {
            "ANALYSIS": "RESEARCH",
            "RESEARCH": "RESEARCH",
            "DESIGN": "PROJECT",
            "IMPLEMENTATION": "FEATURE",
            "INTEGRATION": "FEATURE",
            "VALIDATION": "MAINTENANCE",
            "TESTING": "MAINTENANCE",
            "DOCUMENTATION": "MAINTENANCE",
            "DEPLOYMENT": "OPERATIONS",
            "REVIEW": "MAINTENANCE",
            "MAINTENANCE": "MAINTENANCE",
        }

        return mapping.get(
            normalized,
            "UNKNOWN",
        )

    def _get_session(
        self,
        session_id: str,
    ) -> PlanningSession | None:

        return self._sessions.get(
            str(session_id).strip()
        )

    def _not_found(
        self,
        session_id: str,
    ) -> dict[str, Any]:

        return {
            "success": False,
            "status": "NOT_FOUND",
            "session_id": session_id,
            "error": (
                "Nie znaleziono PlanningSession."
            ),
        }

    def _safe_dict(
        self,
        value: Any,
    ) -> dict[str, Any]:

        if isinstance(value, dict):
            return dict(value)

        return {}

    def _safe_list(
        self,
        value: Any,
    ) -> list[Any]:

        if isinstance(value, list):
            return list(value)

        if isinstance(value, tuple):
            return list(value)

        if isinstance(value, set):
            return list(value)

        if value is None:
            return []

        return [value]

    def _safe_string_list(
        self,
        value: Any,
    ) -> list[str]:

        result: list[str] = []
        seen: set[str] = set()

        for item in self._safe_list(
            value
        ):
            text = str(item).strip()

            if not text:
                continue

            key = text.lower()

            if key in seen:
                continue

            seen.add(key)
            result.append(text)

        return result

    def _optional_string(
        self,
        value: Any,
    ) -> str | None:

        if value is None:
            return None

        normalized = str(
            value
        ).strip()

        return normalized or None
