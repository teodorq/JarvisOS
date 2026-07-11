from __future__ import annotations

from typing import Any

from app.ai.continuous_dev.cycle_memory import CycleMemory
from app.ai.continuous_dev.cycle_state import CycleState
from app.ai.continuous_dev.development_cycle import (
    DevelopmentCycle,
    DevelopmentCycleResult,
    DevelopmentCycleStage,
    DevelopmentCycleStatus,
)
from app.ai.continuous_dev.execution_coordinator import (
    ExecutionCoordinator,
)
from app.ai.continuous_dev.improvement_detector import (
    ImprovementDetector,
)
from app.ai.continuous_dev.improvement_planner import (
    ImprovementPlanner,
)
from app.ai.continuous_dev.rollback_coordinator import (
    RollbackCoordinator,
)
from app.ai.continuous_dev.task_queue import (
    DevelopmentTaskType,
    TaskQueue,
    TaskQueuePriority,
)
from app.ai.continuous_dev.validation_loop import (
    ValidationLoop,
)


class ContinuousDeveloper:

    def __init__(
        self,
        project_root: str,
        research_service: Any | None = None,
        reasoning_service: Any | None = None,
        developer_controller: Any | None = None,
        project_analyzer: Any | None = None,
        improvement_detector: ImprovementDetector | None = None,
        improvement_planner: ImprovementPlanner | None = None,
        task_queue: TaskQueue | None = None,
        validation_loop: ValidationLoop | None = None,
        rollback_coordinator: RollbackCoordinator | None = None,
        execution_coordinator: ExecutionCoordinator | None = None,
        cycle_memory: CycleMemory | None = None,
    ) -> None:

        self.project_root = str(
            project_root
        ).strip()

        if not self.project_root:
            raise ValueError(
                "ContinuousDeveloper wymaga project_root."
            )

        self.research_service = research_service
        self.reasoning_service = reasoning_service
        self.developer_controller = developer_controller
        self.project_analyzer = project_analyzer

        self.improvement_detector = (
            improvement_detector
            if improvement_detector is not None
            else ImprovementDetector()
        )

        self.improvement_planner = (
            improvement_planner
            if improvement_planner is not None
            else ImprovementPlanner()
        )

        self.task_queue = (
            task_queue
            if task_queue is not None
            else TaskQueue()
        )

        self.validation_loop = (
            validation_loop
            if validation_loop is not None
            else ValidationLoop()
        )

        self.rollback_coordinator = (
            rollback_coordinator
            if rollback_coordinator is not None
            else RollbackCoordinator(
                developer_controller=(
                    developer_controller
                )
            )
        )

        self.execution_coordinator = (
            execution_coordinator
            if execution_coordinator is not None
            else ExecutionCoordinator(
                developer_controller=(
                    developer_controller
                ),
                validator=self.validation_loop,
                rollback_coordinator=(
                    self.rollback_coordinator
                ),
            )
        )

        self.cycle_memory = (
            cycle_memory
            if cycle_memory is not None
            else CycleMemory()
        )

        self._cycles: dict[
            str,
            DevelopmentCycle,
        ] = {}

        self._states: dict[
            str,
            CycleState,
        ] = {}

    def create_cycle(
        self,
        objective: str,
        max_iterations: int = 10,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        cycle = DevelopmentCycle(
            project_root=self.project_root,
            objective=objective,
            max_iterations=max_iterations,
            metadata={
                "source": "ContinuousDeveloper",
                **(metadata or {}),
            },
        )

        state = CycleState(
            cycle_id=cycle.cycle_id,
            max_iterations=max_iterations,
            metadata={
                "source": "ContinuousDeveloper",
            },
        )

        self._cycles[
            cycle.cycle_id
        ] = cycle

        self._states[
            cycle.cycle_id
        ] = state

        return {
            "success": True,
            "status": cycle.status,
            "cycle_id": cycle.cycle_id,
            "cycle": cycle.to_dict(),
            "state": state.to_dict(),
        }

    def start_cycle(
        self,
        cycle_id: str,
        auto_approve: bool = False,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        cycle = self._get_cycle(
            cycle_id
        )

        state = self._get_state(
            cycle_id
        )

        if cycle is None or state is None:
            return self._not_found(
                cycle_id
            )

        cycle.start()
        state.activate(
            stage=DevelopmentCycleStage.ANALYZE.value
        )

        return self.run_iteration(
            cycle_id=cycle_id,
            auto_approve=auto_approve,
            context=context,
        )

    def run_iteration(
        self,
        cycle_id: str,
        auto_approve: bool = False,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        cycle = self._get_cycle(
            cycle_id
        )

        state = self._get_state(
            cycle_id
        )

        if cycle is None or state is None:
            return self._not_found(
                cycle_id
            )

        if not cycle.can_continue():
            return {
                "success": False,
                "status": cycle.status,
                "cycle_id": cycle_id,
                "error": (
                    "Cykl nie może być kontynuowany."
                ),
                "summary": cycle.summary(),
            }

        normalized_context = self._safe_dict(
            context
        )

        try:
            cycle.next_iteration()
            state.next_iteration()

            analysis = self._analyze_project(
                objective=cycle.objective,
                context=normalized_context,
            )

            cycle.set_analysis(
                analysis
            )

            state.set_stage(
                DevelopmentCycleStage.DETECT_IMPROVEMENT.value,
                progress=0.20,
            )

            previous_cycles = self.cycle_memory.recent(
                limit=20
            )

            detection = self.improvement_detector.detect(
                analysis=analysis,
                project_context=normalized_context,
                previous_cycles=previous_cycles,
            )

            candidates = detection.get(
                "candidates",
                [],
            )

            cycle.set_detected_improvements(
                candidates
                if isinstance(
                    candidates,
                    list,
                )
                else []
            )

            selected = self.improvement_detector.choose_best(
                detection
            )

            if selected is None:
                result = cycle.complete(
                    result=(
                        DevelopmentCycleResult
                        .NO_CHANGES
                        .value
                    ),
                    report={
                        "success": True,
                        "status": "NO_CHANGES",
                        "message": (
                            "Nie wykryto ulepszeń "
                            "wymagających wykonania."
                        ),
                    },
                )

                state.complete(
                    metadata={
                        "result": "NO_CHANGES",
                    }
                )

                self.cycle_memory.remember(
                    cycle=result,
                    result={
                        "success": True,
                        "result": "NO_CHANGES",
                    },
                )

                return {
                    "success": True,
                    "status": "NO_CHANGES",
                    "cycle_id": cycle_id,
                    "cycle": result,
                }

            cycle.select_improvement(
                selected
            )

            state.set_current_improvement(
                selected.get(
                    "improvement_id"
                )
            )

            research = self._run_research(
                selected,
                normalized_context,
            )

            cycle.set_research(
                research
            )

            reasoning = self._run_reasoning(
                selected,
                research,
                normalized_context,
            )

            cycle.set_reasoning(
                reasoning
            )

            plan = self.improvement_planner.build(
                improvement=selected,
                research_context=research,
                reasoning_context=reasoning,
                project_context=normalized_context,
            )

            cycle.set_plan(
                plan
            )

            tasks = self._enqueue_plan_tasks(
                cycle_id=cycle_id,
                plan=plan,
            )

            next_task = self.task_queue.next_task(
                cycle_id=cycle_id
            )

            if next_task is not None:
                state.set_current_task(
                    next_task.get(
                        "task_id"
                    )
                )

            cycle.set_stage(
                DevelopmentCycleStage.PREPARE_PATCH.value
            )

            coordination = (
                self.execution_coordinator.coordinate(
                    cycle_id=cycle_id,
                    plan=plan,
                    task=next_task,
                    approved=(
                        True
                        if auto_approve
                        else None
                    ),
                    context=normalized_context,
                )
            )

            coordination_status = str(
                coordination.get(
                    "status",
                    "",
                )
            ).upper()

            if coordination_status == (
                "WAITING_FOR_APPROVAL"
            ):
                cycle.set_patch(
                    {
                        "requires_approval": True,
                        "coordination": coordination,
                    }
                )

                state.wait_for_approval(
                    task_id=(
                        next_task.get(
                            "task_id"
                        )
                        if isinstance(
                            next_task,
                            dict,
                        )
                        else None
                    )
                )

                return {
                    "success": True,
                    "status": (
                        "WAITING_FOR_APPROVAL"
                    ),
                    "cycle_id": cycle_id,
                    "selected_improvement": (
                        selected
                    ),
                    "plan": plan,
                    "tasks": tasks,
                    "coordination": coordination,
                    "summary": cycle.summary(),
                }

            return self._finalize_coordination(
                cycle=cycle,
                state=state,
                coordination=coordination,
                selected=selected,
                plan=plan,
                tasks=tasks,
                context=normalized_context,
            )

        except Exception as error:
            message = (
                f"ContinuousDeveloper error: "
                f"{type(error).__name__}: {error}"
            )

            cycle.fail(
                message
            )

            state.fail(
                message
            )

            self.cycle_memory.remember(
                cycle=cycle.to_dict(),
                result={
                    "success": False,
                    "status": "FAILED",
                    "error": message,
                },
            )

            return {
                "success": False,
                "status": "FAILED",
                "cycle_id": cycle_id,
                "error": message,
                "summary": cycle.summary(),
            }

    def approve_cycle(
        self,
        cycle_id: str,
        approved: bool,
        note: str | None = None,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        cycle = self._get_cycle(
            cycle_id
        )

        state = self._get_state(
            cycle_id
        )

        if cycle is None or state is None:
            return self._not_found(
                cycle_id
            )

        cycle.set_approval(
            approved=approved,
            note=note,
        )

        state.approve(
            approved=approved,
            note=note,
        )

        if not approved:
            self.cycle_memory.remember(
                cycle=cycle.to_dict(),
                result={
                    "success": False,
                    "status": "CANCELLED",
                    "result": "CANCELLED",
                },
            )

            return {
                "success": False,
                "status": "CANCELLED",
                "cycle_id": cycle_id,
                "summary": cycle.summary(),
            }

        plan = dict(
            cycle.plan
        )

        next_task = self.task_queue.next_task(
            cycle_id=cycle_id
        )

        coordination = (
            self.execution_coordinator.coordinate(
                cycle_id=cycle_id,
                plan=plan,
                task=next_task,
                approved=True,
                context=self._safe_dict(
                    context
                ),
            )
        )

        return self._finalize_coordination(
            cycle=cycle,
            state=state,
            coordination=coordination,
            selected=dict(
                cycle.selected_improvement
            ),
            plan=plan,
            tasks=self.task_queue.list_tasks(
                cycle_id=cycle_id
            ),
            context=self._safe_dict(
                context
            ),
        )

    def pause_cycle(
        self,
        cycle_id: str,
        reason: str | None = None,
    ) -> dict[str, Any]:

        cycle = self._get_cycle(
            cycle_id
        )

        state = self._get_state(
            cycle_id
        )

        if cycle is None or state is None:
            return self._not_found(
                cycle_id
            )

        cycle.status = (
            DevelopmentCycleStatus.CANCELLED.value
            if reason == "cancel"
            else DevelopmentCycleStatus.CREATED.value
        )

        state.pause(
            reason=reason
        )

        return {
            "success": True,
            "status": state.status,
            "cycle_id": cycle_id,
            "state": state.to_dict(),
        }

    def resume_cycle(
        self,
        cycle_id: str,
        auto_approve: bool = False,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        state = self._get_state(
            cycle_id
        )

        if state is None:
            return self._not_found(
                cycle_id
            )

        state.resume()

        return self.run_iteration(
            cycle_id=cycle_id,
            auto_approve=auto_approve,
            context=context,
        )

    def cancel_cycle(
        self,
        cycle_id: str,
        reason: str | None = None,
    ) -> dict[str, Any]:

        cycle = self._get_cycle(
            cycle_id
        )

        state = self._get_state(
            cycle_id
        )

        if cycle is None or state is None:
            return self._not_found(
                cycle_id
            )

        cycle.cancel(
            reason=reason
        )

        state.cancel(
            reason=reason
        )

        result = {
            "success": False,
            "status": "CANCELLED",
            "result": "CANCELLED",
            "cycle_id": cycle_id,
            "reason": reason,
        }

        self.cycle_memory.remember(
            cycle=cycle.to_dict(),
            result=result,
        )

        return {
            **result,
            "summary": cycle.summary(),
        }

    def get_cycle(
        self,
        cycle_id: str,
    ) -> dict[str, Any] | None:

        cycle = self._get_cycle(
            cycle_id
        )

        if cycle is None:
            return None

        state = self._get_state(
            cycle_id
        )

        return {
            "cycle": cycle.to_dict(),
            "state": (
                state.to_dict()
                if state is not None
                else None
            ),
            "tasks": self.task_queue.list_tasks(
                cycle_id=cycle_id
            ),
        }

    def list_cycles(
        self,
        limit: int = 50,
    ) -> list[dict[str, Any]]:

        cycles = list(
            self._cycles.values()
        )

        cycles.sort(
            key=lambda item: item.updated_at,
            reverse=True,
        )

        return [
            cycle.summary()
            for cycle in cycles[
                :max(
                    1,
                    int(limit),
                )
            ]
        ]

    def system_summary(
        self,
    ) -> dict[str, Any]:

        return {
            "cycles": self.list_cycles(
                limit=100
            ),
            "task_queue": self.task_queue.summary(),
            "memory": self.cycle_memory.summary(),
            "active_cycles": sum(
                1
                for cycle in self._cycles.values()
                if cycle.status
                not in {
                    DevelopmentCycleStatus.COMPLETED.value,
                    DevelopmentCycleStatus.FAILED.value,
                    DevelopmentCycleStatus.CANCELLED.value,
                }
            ),
        }

    def _finalize_coordination(
        self,
        cycle: DevelopmentCycle,
        state: CycleState,
        coordination: dict[str, Any],
        selected: dict[str, Any],
        plan: dict[str, Any],
        tasks: list[dict[str, Any]],
        context: dict[str, Any],
    ) -> dict[str, Any]:

        status = str(
            coordination.get(
                "status",
                "",
            )
        ).upper()

        execution = self._safe_dict(
            coordination.get(
                "execution",
                {},
            )
        )

        validation = self._safe_dict(
            coordination.get(
                "validation",
                {},
            )
        )

        rollback = self._safe_dict(
            coordination.get(
                "rollback",
                {},
            )
        )

        report = self._safe_dict(
            coordination.get(
                "report",
                {},
            )
        )

        if execution:
            cycle.set_execution(
                execution
            )

        if validation:
            cycle.set_validation(
                validation
            )

        if rollback:
            cycle.set_rollback(
                rollback
            )

        if report:
            cycle.set_report(
                report
            )

        next_task = self.task_queue.next_task(
            cycle_id=cycle.cycle_id
        )

        if next_task is not None:
            task_id = next_task[
                "task_id"
            ]

            started = self.task_queue.start_task(
                task_id
            )

            if status == "COMPLETED":
                self.task_queue.complete_task(
                    task_id=task_id,
                    output_data=coordination,
                )

            elif status in {
                "FAILED",
                "ROLLED_BACK",
            }:
                self.task_queue.fail_task(
                    task_id=task_id,
                    error=self._extract_error(
                        coordination
                    ),
                    output_data=coordination,
                    retry=False,
                )

            state.set_current_task(
                task_id
            )

            if isinstance(
                started,
                dict,
            ):
                state.set_current_execution(
                    coordination.get(
                        "coordination_id"
                    )
                )

        if status == "COMPLETED":
            completed_cycle = cycle.complete(
                result=(
                    DevelopmentCycleResult
                    .SUCCESS
                    .value
                ),
                report=report,
            )

            state.complete(
                metadata={
                    "coordination_status": status,
                }
            )

            memory = self.cycle_memory.remember(
                cycle=completed_cycle,
                result={
                    "success": True,
                    "status": "COMPLETED",
                    "result": "SUCCESS",
                    "lessons": report.get(
                        "lessons",
                        [],
                    ),
                },
            )

            return {
                "success": True,
                "status": "COMPLETED",
                "cycle_id": cycle.cycle_id,
                "selected_improvement": selected,
                "plan": plan,
                "tasks": tasks,
                "coordination": coordination,
                "memory": memory,
                "summary": cycle.summary(),
            }

        if status == "ROLLED_BACK":
            completed_cycle = cycle.complete(
                result=(
                    DevelopmentCycleResult
                    .ROLLED_BACK
                    .value
                ),
                report=report,
            )

            state.complete(
                metadata={
                    "coordination_status": status,
                }
            )

            memory = self.cycle_memory.remember(
                cycle=completed_cycle,
                result={
                    "success": False,
                    "status": "ROLLED_BACK",
                    "result": "ROLLED_BACK",
                    "errors": coordination.get(
                        "errors",
                        [],
                    ),
                },
            )

            return {
                "success": False,
                "status": "ROLLED_BACK",
                "cycle_id": cycle.cycle_id,
                "coordination": coordination,
                "memory": memory,
                "summary": cycle.summary(),
            }

        error = self._extract_error(
            coordination
        )

        cycle.fail(
            error=error,
            report=report,
        )

        state.fail(
            error
        )

        memory = self.cycle_memory.remember(
            cycle=cycle.to_dict(),
            result={
                "success": False,
                "status": "FAILED",
                "result": "FAILED",
                "error": error,
            },
        )

        return {
            "success": False,
            "status": "FAILED",
            "cycle_id": cycle.cycle_id,
            "error": error,
            "coordination": coordination,
            "memory": memory,
            "summary": cycle.summary(),
        }

    def _analyze_project(
        self,
        objective: str,
        context: dict[str, Any],
    ) -> dict[str, Any]:

        analyzer = self.project_analyzer

        if analyzer is None:
            return {
                "success": True,
                "status": "COMPLETED",
                "objective": objective,
                "problems": context.get(
                    "problems",
                    [],
                ),
                "warnings": context.get(
                    "warnings",
                    [],
                ),
                "suggestions": context.get(
                    "suggestions",
                    [],
                ),
                "affected_files": context.get(
                    "affected_files",
                    [],
                ),
                "affected_modules": context.get(
                    "affected_modules",
                    [],
                ),
            }

        if hasattr(
            analyzer,
            "analyze",
        ):
            result = analyzer.analyze(
                objective,
                context,
            )

        elif hasattr(
            analyzer,
            "run",
        ):
            result = analyzer.run(
                objective,
                context,
            )

        elif callable(
            analyzer
        ):
            result = analyzer(
                objective,
                context,
            )

        else:
            return {
                "success": False,
                "status": "FAILED",
                "error": (
                    "ProjectAnalyzer nie posiada "
                    "obsługiwanej metody."
                ),
            }

        return self._normalize_result(
            result
        )

    def _run_research(
        self,
        improvement: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:

        service = self.research_service

        if service is None:
            return {
                "success": True,
                "status": "SKIPPED",
                "message": (
                    "ResearchService nie został podłączony."
                ),
            }

        request = (
            f"Przeanalizuj ulepszenie: "
            f"{improvement.get('title', '')}. "
            f"{improvement.get('description', '')}"
        )

        if hasattr(
            service,
            "execute",
        ):
            result = service.execute(
                request
            )

        elif hasattr(
            service,
            "run",
        ):
            result = service.run(
                request
            )

        elif hasattr(
            service,
            "research",
        ):
            result = service.research(
                request
            )

        elif callable(
            service
        ):
            result = service(
                request
            )

        else:
            return {
                "success": False,
                "status": "FAILED",
                "error": (
                    "ResearchService nie posiada "
                    "obsługiwanej metody."
                ),
            }

        return self._normalize_result(
            result
        )

    def _run_reasoning(
        self,
        improvement: dict[str, Any],
        research: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:

        service = self.reasoning_service

        if service is None:
            return {
                "success": True,
                "status": "SKIPPED",
                "message": (
                    "ReasoningService nie został podłączony."
                ),
            }

        request = (
            f"Rozumuj nad ulepszeniem: "
            f"{improvement.get('title', '')}. "
            f"{improvement.get('description', '')}"
        )

        if hasattr(
            service,
            "handle",
        ):
            result = service.handle(
                command=request,
                context={
                    "project_context": context,
                    "research_context": research,
                },
            )

        elif hasattr(
            service,
            "reason",
        ):
            result = service.reason(
                user_request=request,
                research_context=research,
                project_context=context,
                auto_execute=False,
            )

        elif hasattr(
            service,
            "analyze",
        ):
            result = service.analyze(
                user_request=request,
                project_context=context,
            )

        elif callable(
            service
        ):
            result = service(
                request
            )

        else:
            return {
                "success": False,
                "status": "FAILED",
                "error": (
                    "ReasoningService nie posiada "
                    "obsługiwanej metody."
                ),
            }

        return self._normalize_result(
            result
        )

    def _enqueue_plan_tasks(
        self,
        cycle_id: str,
        plan: dict[str, Any],
    ) -> list[dict[str, Any]]:

        steps = plan.get(
            "steps",
            [],
        )

        if not isinstance(
            steps,
            list,
        ):
            return []

        step_to_task: dict[
            str,
            str,
        ] = {}

        created: list[
            dict[str, Any]
        ] = []

        for step in steps:
            if not isinstance(
                step,
                dict,
            ):
                continue

            task = self.task_queue.add_task(
                cycle_id=cycle_id,
                title=str(
                    step.get(
                        "name",
                        "Nieznane zadanie",
                    )
                ),
                description=str(
                    step.get(
                        "description",
                        "",
                    )
                ),
                task_type=str(
                    step.get(
                        "step_type",
                        DevelopmentTaskType.UNKNOWN.value,
                    )
                ),
                priority=self._step_priority(
                    step
                ),
                order=self._safe_int(
                    step.get(
                        "order",
                        len(created) + 1,
                    ),
                    len(created) + 1,
                ),
                dependencies=[],
                max_attempts=3,
                input_data=self._safe_dict(
                    step.get(
                        "inputs",
                        {},
                    )
                ),
                metadata={
                    "plan_id": plan.get(
                        "plan_id"
                    ),
                    "plan_step_id": step.get(
                        "step_id"
                    ),
                    "requires_approval": step.get(
                        "requires_approval",
                        False,
                    ),
                },
            )

            step_id = str(
                step.get(
                    "step_id",
                    "",
                )
            )

            if step_id:
                step_to_task[
                    step_id
                ] = task["task_id"]

            created.append(
                task
            )

        for step, task in zip(
            [
                item
                for item in steps
                if isinstance(
                    item,
                    dict,
                )
            ],
            created,
        ):
            dependency_task_ids = []

            for dependency_step_id in (
                step.get(
                    "dependencies",
                    [],
                )
                or []
            ):
                task_id = step_to_task.get(
                    str(
                        dependency_step_id
                    )
                )

                if task_id:
                    dependency_task_ids.append(
                        task_id
                    )

            task_object = self.task_queue._get_task(
                task["task_id"]
            )

            if task_object is not None:
                task_object.dependencies = (
                    dependency_task_ids
                )

        self.task_queue._refresh_states()
        self.task_queue.save()

        return self.task_queue.list_tasks(
            cycle_id=cycle_id
        )

    def _step_priority(
        self,
        step: dict[str, Any],
    ) -> str:

        step_type = str(
            step.get(
                "step_type",
                "",
            )
        ).upper()

        if step_type in {
            "EXECUTE",
            "VALIDATE",
            "ROLLBACK",
            "APPROVE",
        }:
            return TaskQueuePriority.HIGH.value

        if step_type in {
            "ANALYZE",
            "RESEARCH",
            "REASON",
            "PREPARE_PATCH",
        }:
            return TaskQueuePriority.MEDIUM.value

        return TaskQueuePriority.LOW.value

    def _normalize_result(
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

        return {
            "success": True,
            "status": "COMPLETED",
            "result": result,
        }

    def _extract_error(
        self,
        result: dict[str, Any],
    ) -> str:

        for key in (
            "error",
            "message",
            "details",
        ):
            value = result.get(
                key
            )

            if value:
                return str(
                    value
                )

        return (
            "Continuous Developer zakończył "
            "operację niepowodzeniem."
        )

    def _get_cycle(
        self,
        cycle_id: str,
    ) -> DevelopmentCycle | None:

        return self._cycles.get(
            str(cycle_id).strip()
        )

    def _get_state(
        self,
        cycle_id: str,
    ) -> CycleState | None:

        return self._states.get(
            str(cycle_id).strip()
        )

    def _not_found(
        self,
        cycle_id: str,
    ) -> dict[str, Any]:

        return {
            "success": False,
            "status": "NOT_FOUND",
            "cycle_id": cycle_id,
            "error": (
                "Nie znaleziono cyklu Continuous Developer."
            ),
        }

    def _safe_int(
        self,
        value: Any,
        default: int,
    ) -> int:

        try:
            return int(
                value
            )
        except (
            TypeError,
            ValueError,
        ):
            return default

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
