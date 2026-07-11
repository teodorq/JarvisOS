from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from app.autodev.autodev_pipeline import (
    AutoDevPipeline,
    AutoDevPipelinePolicy,
)
from app.autodev.autonomous_planner import AutonomousPlanner
from app.autodev.autonomous_task_queue import (
    TaskPriority,
    TaskStatus,
)
from app.autodev.developer_agent import DeveloperAgent
from app.autodev.developer_controller import DeveloperController
from app.autodev.developer_request import DeveloperRequest
from app.autodev.reasoning_memory import ReasoningMemory


@dataclass(slots=True)
class AutonomousDevControllerPolicy:
    project_root: str = "C:/JarvisAI"
    queue_storage_path: str = (
        "data/autodev/autonomous_task_queue.json"
    )
    worker_count: int = 1
    auto_approve: bool = False
    auto_execute: bool = True
    auto_rollback: bool = True
    max_parallel_tasks: int = 1
    auto_start_pipeline: bool = True
    max_backlog_size: int = 100
    default_priority: TaskPriority = TaskPriority.NORMAL

    def validate(self) -> None:
        if not self.project_root.strip():
            raise ValueError("project_root cannot be empty")

        if not self.queue_storage_path.strip():
            raise ValueError(
                "queue_storage_path cannot be empty"
            )

        if self.worker_count < 1:
            raise ValueError(
                "worker_count must be at least 1"
            )

        if self.max_parallel_tasks < 1:
            raise ValueError(
                "max_parallel_tasks must be at least 1"
            )

        if self.max_parallel_tasks > self.worker_count:
            raise ValueError(
                "max_parallel_tasks cannot exceed worker_count"
            )

        if self.max_backlog_size < 1:
            raise ValueError(
                "max_backlog_size must be at least 1"
            )


class AutonomousDevController:

    COMMAND_PREFIXES = (
        "autonomous dev",
        "autonomous autodev",
        "autodev autonomous",
        "autonomiczny autodev",
        "autonomiczny rozwój",
        "kolejka autodev",
        "status autodev",
        "developer 2.0",
        "developer backlog",
    )

    PRIORITY_KEYWORDS = {
        TaskPriority.CRITICAL: (
            "critical",
            "krytyczny",
            "security",
            "bezpieczeństwo",
            "data loss",
            "utrata danych",
            "startup failure",
            "nie uruchamia się",
        ),
        TaskPriority.HIGH: (
            "bug",
            "błąd",
            "error",
            "failed",
            "awaria",
            "regression",
            "test failure",
            "testy nie przechodzą",
        ),
        TaskPriority.NORMAL: (
            "improve",
            "ulepsz",
            "refactor",
            "optymalizuj",
            "feature",
            "funkcja",
        ),
        TaskPriority.LOW: (
            "cleanup",
            "porządki",
            "docs",
            "documentation",
            "komentarze",
            "cosmetic",
        ),
    }

    def __init__(
        self,
        *,
        policy: AutonomousDevControllerPolicy | None = None,
        pipeline: AutoDevPipeline | None = None,
        planner: AutonomousPlanner | None = None,
        developer_agent: DeveloperAgent | None = None,
        developer_controller: DeveloperController | None = None,
    ) -> None:

        self.policy = policy or AutonomousDevControllerPolicy()
        self.policy.validate()

        pipeline_policy = AutoDevPipelinePolicy(
            project_root=self.policy.project_root,
            queue_storage_path=self.policy.queue_storage_path,
            worker_count=self.policy.worker_count,
            auto_approve=self.policy.auto_approve,
            auto_execute=self.policy.auto_execute,
            auto_rollback=self.policy.auto_rollback,
            max_parallel_tasks=self.policy.max_parallel_tasks,
        )

        self.pipeline = pipeline or AutoDevPipeline(
            policy=pipeline_policy
        )

        self.planner = planner or AutonomousPlanner(
            project_root=self.policy.project_root
        )

        self.developer_agent = developer_agent or DeveloperAgent()

        self.developer_controller = (
            developer_controller
            or DeveloperController(
                project_root=self.policy.project_root
            )
        )

        self.last_scan: dict[str, Any] | None = None
        self.last_planning_cycle: dict[str, Any] | None = None
        self.last_generation_cycle: dict[str, Any] | None = None
        self.last_autonomous_loop: dict[str, Any] | None = None
        self.learning_memory = ReasoningMemory()

    def can_handle(
        self,
        command: str,
    ) -> bool:

        normalized = str(command).strip().casefold()

        return any(
            prefix in normalized
            for prefix in self.COMMAND_PREFIXES
        )

    def handle(
        self,
        command: str,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        normalized_command = str(command).strip()
        normalized = normalized_command.casefold()
        context = dict(context or {})

        if not normalized_command:
            return {
                "success": False,
                "status": "EMPTY_COMMAND",
                "error": (
                    "AutonomousDevController "
                    "otrzymał puste polecenie."
                ),
            }

        if (
            "decision ranking" in normalized
            or "ranking zadań" in normalized
            or "ranking zadan" in normalized
            or "wybierz najlepsze zadanie" in normalized
            or "najlepsze zadanie autodev" in normalized
        ):
            return self.decision_report(
                limit=self._safe_positive_int(
                    context.get("limit"),
                    10,
                )
            )

        if (
            "autonomous loop" in normalized
            or "autonomiczna pętla" in normalized
            or "autonomiczna petla" in normalized
            or "rozwijaj projekt autonomicznie" in normalized
            or "pracuj autonomicznie" in normalized
        ):
            return self.run_autonomous_loop(
                max_cycles=self._safe_positive_int(
                    context.get("max_cycles"),
                    5,
                ),
                context=context,
                auto_approve=context.get("auto_approve"),
                auto_execute=context.get("auto_execute"),
                stop_on_failure=bool(
                    context.get("stop_on_failure", True)
                ),
            )

        if (
            "generation cycle" in normalized
            or "cykl generowania" in normalized
            or "generuj zmianę" in normalized
            or "generuj zmiane" in normalized
        ):
            return self.run_generation_cycle(
                context=context
            )

        if (
            "planning cycle" in normalized
            or "cykl planowania" in normalized
            or "zaplanuj następne" in normalized
            or "zaplanuj nastepne" in normalized
        ):
            return self.run_planning_cycle(
                context_by_module=context.get(
                    "context_by_module"
                )
            )

        if (
            "scan" in normalized
            or "skanuj" in normalized
            or "analizuj projekt" in normalized
        ):
            return self.scan_project(
                context_by_module=context.get(
                    "context_by_module"
                )
            )

        if (
            "health" in normalized
            or "diagnostyka" in normalized
            or "stan systemu autodev" in normalized
        ):
            return self.health_report()

        if (
            "planner status" in normalized
            or "plan status" in normalized
        ):
            return {
                "success": True,
                "status": "PLANNER_STATUS",
                "last_scan": self.last_scan,
                "last_planning_cycle": self.last_planning_cycle,
                "last_generation_cycle": self.last_generation_cycle,
                "planner": self.planner.status(),
            }

        if (
            "next planned" in normalized
            or "następny plan" in normalized
            or "nastepny plan" in normalized
        ):
            return self.planner.next_task()

        if "status" in normalized:
            return {
                "success": True,
                "status": "STATUS",
                "pipeline": self.pipeline.status(),
                "backlog": self.backlog_summary(),
                "planner": self.planner.status(),
                "last_planning_cycle": self.last_planning_cycle,
                "last_generation_cycle": self.last_generation_cycle,
            }

        if (
            "list" in normalized
            or "lista" in normalized
            or "backlog" in normalized
        ):
            return {
                "success": True,
                "status": "BACKLOG",
                "tasks": self.list_tasks(),
                "summary": self.backlog_summary(),
                "planned_tasks": (
                    self.planner.backlog.list_items()
                ),
            }

        if (
            "next" in normalized
            or "następne zadanie" in normalized
            or "nastepne zadanie" in normalized
        ):
            return self.next_task()

        if (
            "start" in normalized
            or "uruchom" in normalized
        ):
            started = self.pipeline.start()

            return {
                "success": True,
                "status": (
                    "STARTED"
                    if started
                    else "ALREADY_RUNNING"
                ),
                "pipeline": self.pipeline.status(),
            }

        if (
            "stop" in normalized
            or "zatrzymaj" in normalized
        ):
            stopped = self.pipeline.stop(wait=False)

            return {
                "success": True,
                "status": (
                    "STOPPED"
                    if stopped
                    else "ALREADY_STOPPED"
                ),
                "pipeline": self.pipeline.status(),
            }

        if (
            "pause" in normalized
            or "wstrzymaj" in normalized
        ):
            paused = self.pipeline.pause()

            return {
                "success": paused,
                "status": (
                    "PAUSED"
                    if paused
                    else "NOT_RUNNING"
                ),
                "pipeline": self.pipeline.status(),
            }

        if (
            "resume" in normalized
            or "wznów" in normalized
            or "wznow" in normalized
        ):
            resumed = self.pipeline.resume()

            return {
                "success": resumed,
                "status": (
                    "RUNNING"
                    if resumed
                    else "NOT_PAUSED"
                ),
                "pipeline": self.pipeline.status(),
            }

        return self.queue_goal(
            goal=normalized_command,
            source=str(context.get("source", "Brain")),
            context=context,
        )

    def decision_report(
        self,
        *,
        limit: int = 10,
    ) -> dict[str, Any]:
        queue = getattr(self.pipeline, "queue", None)

        if queue is None:
            return {
                "success": False,
                "status": "QUEUE_UNAVAILABLE",
                "ranked_tasks": [],
            }

        ranking_method = getattr(
            queue,
            "ranked_ready_tasks",
            None,
        )

        if not callable(ranking_method):
            return {
                "success": False,
                "status": "DECISION_ENGINE_UNAVAILABLE",
                "ranked_tasks": [],
            }

        ranked_tasks = ranking_method(
            limit=max(1, int(limit))
        )
        selected = ranked_tasks[0] if ranked_tasks else None

        return {
            "success": True,
            "status": (
                "TASK_SELECTED"
                if selected is not None
                else "NO_READY_TASKS"
            ),
            "selected": selected,
            "ranked_tasks": ranked_tasks,
            "ready_count": len(ranked_tasks),
            "decision_engine_version": "1.0.0",
        }

    def run_autonomous_loop(
        self,
        *,
        max_cycles: int = 5,
        context: dict[str, Any] | None = None,
        auto_approve: bool | None = None,
        auto_execute: bool | None = None,
        stop_on_failure: bool = True,
    ) -> dict[str, Any]:

        normalized_context = dict(context or {})
        cycles_limit = self._safe_positive_int(
            max_cycles,
            5,
        )

        approve_changes = (
            self.policy.auto_approve
            if auto_approve is None
            else bool(auto_approve)
        )
        execute_changes = (
            self.policy.auto_execute
            if auto_execute is None
            else bool(auto_execute)
        )

        started_pipeline = False
        if self.policy.auto_start_pipeline:
            started_pipeline = self.pipeline.start()

        cycle_results: list[dict[str, Any]] = []
        completed_cycles = 0
        loop_status = "COMPLETED"
        success = True
        blocking_reason = ""

        for cycle_number in range(1, cycles_limit + 1):
            self.last_planning_cycle = None
            self.last_generation_cycle = None

            generation = self.run_generation_cycle(
                context=normalized_context
            )

            cycle_result: dict[str, Any] = {
                "cycle": cycle_number,
                "generation": generation,
            }
            generation_status = str(
                generation.get("status", "UNKNOWN")
            ).upper()

            if generation_status == "NO_TASKS":
                loop_status = "NO_TASKS"
                cycle_results.append(cycle_result)
                break

            if generation_status == "CODE_INPUT_REQUIRED":
                loop_status = "WAITING_FOR_CODE_INPUT"
                blocking_reason = (
                    "Planner nie dostarczył kompletnego kodu "
                    "potrzebnego do utworzenia patcha."
                )
                cycle_results.append(cycle_result)
                break

            if not generation.get("success", False):
                success = False
                loop_status = "GENERATION_FAILED"
                blocking_reason = str(
                    generation.get(
                        "message",
                        generation.get("error", ""),
                    )
                )
                cycle_results.append(cycle_result)

                if stop_on_failure:
                    break

                continue

            if not approve_changes:
                loop_status = "WAITING_FOR_APPROVAL"
                blocking_reason = (
                    "Automatyczna akceptacja jest wyłączona."
                )
                cycle_results.append(cycle_result)
                break

            execution = self.approve_generated_change(
                auto_execute=execute_changes
            )
            cycle_result["execution"] = execution
            cycle_results.append(cycle_result)

            execution_status = str(
                execution.get("status", "UNKNOWN")
            ).upper()

            if not execute_changes:
                loop_status = "APPROVED_NOT_EXECUTED"
                blocking_reason = (
                    "Zmiana została zatwierdzona, ale "
                    "automatyczne wykonanie jest wyłączone."
                )
                break

            if execution.get("success", False):
                completed_cycles += 1
                continue

            success = False
            loop_status = (
                execution_status
                if execution_status
                else "EXECUTION_FAILED"
            )
            blocking_reason = str(
                execution.get(
                    "message",
                    execution.get("error", ""),
                )
            )

            if stop_on_failure:
                break

        else:
            loop_status = "MAX_CYCLES_REACHED"

        result = {
            "success": success,
            "status": loop_status,
            "max_cycles": cycles_limit,
            "completed_cycles": completed_cycles,
            "cycles_attempted": len(cycle_results),
            "auto_approve": approve_changes,
            "auto_execute": execute_changes,
            "stop_on_failure": bool(stop_on_failure),
            "pipeline_started": started_pipeline,
            "blocking_reason": blocking_reason,
            "cycles": cycle_results,
            "pipeline": self.pipeline.status(),
            "backlog": self.backlog_summary(),
        }

        self.last_autonomous_loop = dict(result)
        self._remember_learning(
            success=success,
            status=loop_status,
            lessons=[
                (
                    f"Autonomiczna pętla wykonała "
                    f"{completed_cycles} pełnych cykli."
                )
            ],
            metadata={
                "stage": "autonomous_loop",
                "cycles_attempted": len(cycle_results),
                "max_cycles": cycles_limit,
            },
        )
        return result

    @staticmethod
    def _safe_positive_int(
        value: Any,
        default: int,
    ) -> int:
        try:
            normalized = int(value)
        except (TypeError, ValueError):
            return default

        return normalized if normalized > 0 else default

    def scan_project(
        self,
        context_by_module: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:

        result = self.planner.scan_and_plan(
            context_by_module=context_by_module
        )

        self.last_scan = dict(result)

        return {
            "success": True,
            "status": "PROJECT_SCANNED",
            **result,
        }

    def run_planning_cycle(
        self,
        context_by_module: dict[str, dict[str, Any]] | None = None,
    ) -> dict[str, Any]:

        scan_result = self.scan_project(
            context_by_module=context_by_module
        )

        selected = self.planner.claim_next_task()

        if selected.get("task") is None:
            result = {
                "success": True,
                "status": "NO_TASKS",
                "scan": scan_result,
                "task": None,
            }

            self.last_planning_cycle = dict(result)
            return result

        task = dict(selected["task"])

        try:
            plan = self.developer_agent.prepare_planned_task(
                task
            )
        except Exception as error:
            task_id = str(task.get("task_id", ""))

            if task_id:
                self.planner.fail_task(
                    task_id,
                    str(error),
                )

            result = {
                "success": False,
                "status": "PLANNING_FAILED",
                "task": task,
                "error": (
                    f"{type(error).__name__}: {error}"
                ),
                "scan": scan_result,
            }

            self.last_planning_cycle = dict(result)
            return result

        result = {
            "success": True,
            "status": "READY_FOR_CODE_GENERATION",
            "task": task,
            "plan": plan,
            "scan": scan_result,
        }

        self.last_planning_cycle = dict(result)
        return result

    def run_generation_cycle(
        self,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        context = dict(context or {})

        planning = self.last_planning_cycle

        if (
            planning is None
            or planning.get("status")
            != "READY_FOR_CODE_GENERATION"
        ):
            planning = self.run_planning_cycle(
                context_by_module=context.get(
                    "context_by_module"
                )
            )

        if planning.get("status") != (
            "READY_FOR_CODE_GENERATION"
        ):
            self.last_generation_cycle = dict(planning)
            return planning

        task = dict(planning.get("task") or {})
        plan = dict(planning.get("plan") or {})

        request = self._build_developer_request(
            task=task,
            plan=plan,
            context=context,
        )

        valid, errors = request.validate()

        if not valid:
            result = {
                "success": False,
                "status": "CODE_INPUT_REQUIRED",
                "errors": errors,
                "task": task,
                "plan": plan,
                "required": self._required_code_fields(
                    request.mode
                ),
            }

            self.last_generation_cycle = dict(result)
            self._remember_learning(
                success=False,
                status="CODE_INPUT_REQUIRED",
                task=task,
                errors=errors,
                lessons=[
                    "Brak danych potrzebnych do wygenerowania patcha."
                ],
            )
            return result

        self.developer_controller.reset()

        prepared = self.developer_controller.prepare(
            request
        )

        result = {
            "success": prepared.success,
            "status": prepared.status,
            "message": prepared.message,
            "preview": prepared.preview,
            "errors": list(prepared.errors),
            "task": task,
            "plan": plan,
            "request": {
                "goal": request.goal,
                "target": request.target,
                "mode": request.mode,
                "path": request.path,
                "function_name": request.function_name,
                "files_count": len(request.replacements),
            },
        }

        if prepared.success:
            task_id = str(task.get("task_id", ""))

            if task_id:
                result["planner_task_id"] = task_id

        self.last_generation_cycle = dict(result)
        self._remember_learning(
            success=prepared.success,
            status=prepared.status,
            task=task,
            errors=list(prepared.errors),
            lessons=[prepared.message],
            metadata={
                "stage": "prepare",
                "preview_ready": bool(prepared.preview),
            },
        )
        return result

    def _build_developer_request(
        self,
        *,
        task: dict[str, Any],
        plan: dict[str, Any],
        context: dict[str, Any],
    ) -> DeveloperRequest:

        mode = str(
            context.get("mode", "file")
        ).strip()

        target = str(
            context.get(
                "target",
                task.get("target", ""),
            )
        ).strip()

        goal = str(
            context.get(
                "goal",
                plan.get(
                    "goal",
                    task.get(
                        "description",
                        task.get("title", ""),
                    ),
                ),
            )
        ).strip()

        return DeveloperRequest(
            goal=goal,
            target=target,
            mode=mode,
            path=str(
                context.get(
                    "path",
                    target,
                )
            ).strip(),
            proposed_content=str(
                context.get(
                    "proposed_content",
                    "",
                )
            ),
            function_name=str(
                context.get(
                    "function_name",
                    "",
                )
            ).strip(),
            new_function_code=str(
                context.get(
                    "new_function_code",
                    "",
                )
            ),
            replacements=dict(
                context.get("replacements") or {}
            ),
            metadata={
                "source": "AutonomousDevController",
                "planner_task_id": str(
                    task.get("task_id", "")
                ),
                "priority_score": str(
                    task.get("priority_score", "")
                ),
                "severity": str(
                    task.get("severity", "")
                ),
                **{
                    str(key): str(value)
                    for key, value in dict(
                        context.get("metadata") or {}
                    ).items()
                },
            },
        )

    def _required_code_fields(
        self,
        mode: str,
    ) -> list[str]:

        if mode == "function":
            return [
                "path",
                "function_name",
                "new_function_code",
            ]

        if mode == "multi_file":
            return [
                "replacements",
            ]

        return [
            "path",
            "proposed_content",
        ]

    def approve_generated_change(
        self,
        *,
        auto_execute: bool = False,
    ) -> dict[str, Any]:

        approval = self.developer_controller.approve()

        if not approval.success:
            return approval.as_dict()

        if not auto_execute:
            return approval.as_dict()

        execution = self.developer_controller.execute(
            auto_rollback=self.policy.auto_rollback
        )

        self._remember_learning(
            success=execution.success,
            status=execution.status,
            task=(
                dict(
                    (self.last_generation_cycle or {}).get(
                        "task"
                    )
                    or {}
                )
            ),
            errors=list(execution.errors),
            lessons=[execution.message],
            metadata={
                "stage": "execute",
                "rollback": (
                    execution.status
                    in {
                        "failed_and_rolled_back",
                        "rolled_back",
                    }
                ),
            },
        )

        if execution.success:
            task_id = ""

            if self.last_generation_cycle:
                task_id = str(
                    self.last_generation_cycle.get(
                        "planner_task_id",
                        "",
                    )
                )

            if task_id:
                self.planner.complete_task(task_id)

        return execution.as_dict()

    def _remember_learning(
        self,
        *,
        success: bool,
        status: str,
        task: dict[str, Any] | None = None,
        errors: list[str] | None = None,
        lessons: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        task = dict(task or {})

        record = {
            "success": bool(success),
            "status": str(status),
            "goal": str(
                task.get(
                    "description",
                    task.get("title", ""),
                )
            ),
            "target": str(task.get("target", "")),
            "task_id": str(task.get("task_id", "")),
            "errors": list(errors or []),
            "lessons": list(lessons or []),
            "metadata": dict(metadata or {}),
        }

        self.learning_memory.remember(record)
        return record

    def learning_summary(
        self,
    ) -> dict[str, Any]:

        return self.learning_memory.summary_dict()

    def queue_goal(
        self,
        *,
        goal: str,
        source: str = "autonomous_dev_controller",
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        context = dict(context or {})

        priority = self.calculate_priority(
            goal=goal,
            context=context,
        )

        task = self.submit_goal(
            goal=goal,
            source=source,
            context=context,
            priority=priority,
        )

        started = False

        if self.policy.auto_start_pipeline:
            started = bool(self.pipeline.start())

        return {
            "success": True,
            "status": "QUEUED",
            "task_id": task["task_id"],
            "priority": priority.value,
            "pipeline_started": started,
            "task": task,
        }

    def submit_goal(
        self,
        *,
        goal: str,
        source: str = "autonomous_dev_controller",
        context: dict[str, Any] | None = None,
        priority: TaskPriority | None = None,
    ) -> dict[str, Any]:

        normalized_goal = str(goal).strip()

        if not normalized_goal:
            raise ValueError(
                "Cel AutoDev nie może być pusty."
            )

        context = dict(context or {})

        if len(self.list_tasks()) >= self.policy.max_backlog_size:
            raise RuntimeError(
                "Backlog AutoDev osiągnął limit."
            )

        selected_priority = priority or self.calculate_priority(
            goal=normalized_goal,
            context=context,
        )

        task = self.pipeline.submit(
            title=normalized_goal[:120],
            description=normalized_goal,
            source=source,
            priority=selected_priority,
            payload={
                "goal": normalized_goal,
                "target": context.get("target", ""),
                "mode": context.get("mode", "file"),
                "path": context.get("path", ""),
                "proposed_content": context.get(
                    "proposed_content",
                    "",
                ),
                "function_name": context.get(
                    "function_name",
                    "",
                ),
                "new_function_code": context.get(
                    "new_function_code",
                    "",
                ),
                "replacements": context.get(
                    "replacements",
                    {},
                ),
                "metadata": {
                    "source": source,
                    "priority_reason": self.priority_reason(
                        normalized_goal
                    ),
                    "learning": {
                        "attempts": 0,
                        "last_result": "",
                        "lessons": [],
                    },
                    **dict(context.get("metadata") or {}),
                },
                "auto_approve": context.get(
                    "auto_approve",
                    self.policy.auto_approve,
                ),
                "auto_execute": context.get(
                    "auto_execute",
                    self.policy.auto_execute,
                ),
                "auto_rollback": context.get(
                    "auto_rollback",
                    self.policy.auto_rollback,
                ),
            },
            tags=context.get(
                "tags",
                [
                    "autonomous-dev",
                    selected_priority.value.lower(),
                ],
            ),
            dependencies=context.get("dependencies"),
        )

        return task.to_dict()

    def calculate_priority(
        self,
        *,
        goal: str,
        context: dict[str, Any] | None = None,
    ) -> TaskPriority:

        context = dict(context or {})

        explicit_priority = context.get("priority")

        if explicit_priority:
            try:
                return TaskPriority(
                    str(explicit_priority).upper()
                )
            except ValueError:
                pass

        normalized = str(goal).casefold()

        for priority in (
            TaskPriority.CRITICAL,
            TaskPriority.HIGH,
            TaskPriority.NORMAL,
            TaskPriority.LOW,
        ):
            keywords = self.PRIORITY_KEYWORDS.get(
                priority,
                (),
            )

            if any(
                keyword.casefold() in normalized
                for keyword in keywords
            ):
                return priority

        return self.policy.default_priority

    def priority_reason(
        self,
        goal: str,
    ) -> str:

        normalized = str(goal).casefold()

        for priority, keywords in self.PRIORITY_KEYWORDS.items():
            for keyword in keywords:
                if keyword.casefold() in normalized:
                    return (
                        f"Priorytet {priority.value} "
                        f"przez słowo: {keyword}"
                    )

        return (
            "Użyto domyślnego priorytetu "
            f"{self.policy.default_priority.value}."
        )

    def next_task(
        self,
    ) -> dict[str, Any]:

        statuses = [
            status
            for status in (
                getattr(TaskStatus, "PENDING", None),
                getattr(TaskStatus, "READY", None),
                getattr(TaskStatus, "QUEUED", None),
            )
            if status is not None
        ]

        tasks = self.pipeline.list_tasks(
            statuses=statuses or None,
            limit=1,
        )

        if not tasks:
            planned = self.planner.next_task()

            if planned.get("task") is not None:
                return {
                    "success": True,
                    "status": "PLANNED_TASK",
                    "task": planned["task"],
                }

            return {
                "success": True,
                "status": "NO_TASKS",
                "task": None,
            }

        return {
            "success": True,
            "status": "NEXT_TASK",
            "task": tasks[0],
        }

    def task_status(
        self,
        task_id: str,
    ) -> dict[str, Any]:

        task = self.pipeline.get_task(task_id)

        if task is None:
            return {
                "success": False,
                "status": "NOT_FOUND",
                "task_id": task_id,
            }

        return {
            "success": True,
            "status": task.status.value,
            "task": task.to_dict(),
        }

    def cancel_task(
        self,
        task_id: str,
        *,
        reason: str = "Cancelled by controller",
    ) -> dict[str, Any]:

        task = self.pipeline.cancel_task(
            task_id,
            reason=reason,
        )

        return {
            "success": True,
            "status": task.status.value,
            "task": task.to_dict(),
        }

    def retry_task(
        self,
        task_id: str,
        *,
        reset_attempts: bool = False,
    ) -> dict[str, Any]:

        task = self.pipeline.retry_task(
            task_id,
            reset_attempts=reset_attempts,
        )

        return {
            "success": True,
            "status": task.status.value,
            "task": task.to_dict(),
        }

    def list_tasks(
        self,
        *,
        status: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:

        statuses = None

        if status:
            statuses = [TaskStatus(status)]

        return self.pipeline.list_tasks(
            statuses=statuses,
            limit=limit,
        )

    def backlog_summary(
        self,
    ) -> dict[str, Any]:

        tasks = self.list_tasks()

        by_status: dict[str, int] = {}
        by_priority: dict[str, int] = {}

        for task in tasks:
            status = str(task.get("status", "UNKNOWN"))
            priority = str(task.get("priority", "UNKNOWN"))

            by_status[status] = by_status.get(status, 0) + 1
            by_priority[priority] = (
                by_priority.get(priority, 0) + 1
            )

        return {
            "total": len(tasks),
            "by_status": by_status,
            "by_priority": by_priority,
            "limit": self.policy.max_backlog_size,
        }

    @staticmethod
    def _metric_value(
        metrics: dict[str, Any],
        key: str,
    ) -> int:
        try:
            return int(metrics.get(key, 0) or 0)
        except (TypeError, ValueError):
            return 0

    def health_report(
        self,
    ) -> dict[str, Any]:
        pipeline = dict(self.pipeline.status() or {})
        backlog = self.backlog_summary()
        queue_metrics = dict(
            pipeline.get("queue_metrics") or {}
        )
        scheduler_metrics = dict(
            pipeline.get("scheduler_metrics") or {}
        )
        workers = list(pipeline.get("workers") or [])

        issues: list[str] = []
        warnings: list[str] = []

        state = str(pipeline.get("state", "unknown"))
        last_error = pipeline.get("last_error")

        if state.casefold() == "failed":
            issues.append("Scheduler AutoDev jest w stanie FAILED.")

        if last_error:
            issues.append(f"Pipeline zgłasza błąd: {last_error}")

        failed = self._metric_value(
            queue_metrics,
            "failed",
        )
        blocked = self._metric_value(
            queue_metrics,
            "blocked",
        )
        worker_errors = self._metric_value(
            scheduler_metrics,
            "worker_errors",
        )

        if failed:
            warnings.append(
                f"Liczba nieudanych zadań: {failed}."
            )

        if blocked:
            warnings.append(
                f"Liczba zablokowanych zadań: {blocked}."
            )

        if worker_errors:
            warnings.append(
                f"Liczba błędów workerów: {worker_errors}."
            )

        enabled_workers = sum(
            1
            for worker in workers
            if bool(worker.get("enabled", True))
        )

        if backlog["total"] > 0 and enabled_workers == 0:
            issues.append(
                "Backlog zawiera zadania, ale brak aktywnych workerów."
            )

        if issues:
            health = "FAILED"
        elif warnings:
            health = "DEGRADED"
        else:
            health = "HEALTHY"

        return {
            "success": not issues,
            "status": health,
            "state": state,
            "issues": issues,
            "warnings": warnings,
            "backlog": backlog,
            "queue_metrics": queue_metrics,
            "scheduler_metrics": scheduler_metrics,
            "workers_total": len(workers),
            "workers_enabled": enabled_workers,
        }

    def status(
        self,
    ) -> dict[str, Any]:

        return {
            "policy": asdict(self.policy),
            "pipeline": self.pipeline.status(),
            "backlog": self.backlog_summary(),
            "planner": self.planner.status(),
            "last_scan": self.last_scan,
            "last_planning_cycle": self.last_planning_cycle,
            "last_generation_cycle": self.last_generation_cycle,
            "last_autonomous_loop": self.last_autonomous_loop,
            "learning": self.learning_summary(),
        }
