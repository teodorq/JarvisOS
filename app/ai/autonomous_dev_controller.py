"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import re
import threading
import time
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
from app.autodev.code_generator import CodeGenerator
from app.autodev.developer_agent import DeveloperAgent
from app.autodev.developer_controller import DeveloperController
from app.autodev.developer_request import DeveloperRequest
from app.autodev.reasoning_memory import ReasoningMemory
from app.autodev.error_reporting import AutoDevErrorReporter
from app.ai.autonomous_dev_orchestration_service import AutonomousDevOrchestrationService
from app.core.project_paths import resolve_project_root


@dataclass(slots=True)
class AutonomousDevControllerPolicy:
    project_root: str = field(
        default_factory=lambda: str(
            resolve_project_root()
        )
    )
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


_AUTONOMOUS_DEV_ORCHESTRATION = AutonomousDevOrchestrationService()


class AutonomousDevController:

    COMMAND_PREFIXES = (
        "autonomous dev",
        "autonomous autodev",
        "autodev autonomous",
        "autonomiczny autodev",
        "autonomiczny rozwój",
        "kolejka autodev",
        "background autodev",
        "autodev background",
        "developer 2.0",
        "developer backlog",
        "rozwijaj projekt",
        "rozwój projektu",
        "rozwoj projektu",
        "pracuj nad projektem",
        "pracuj autonomicznie",
        "autonomiczna pętla",
        "autonomiczna petla",
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
        code_generator: CodeGenerator | None = None,
    ) -> None:

        self.policy = policy or AutonomousDevControllerPolicy()
        self.policy.validate()
        self.project_root = self.policy.project_root

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
        self.code_generator = code_generator or CodeGenerator(
            project_root=self.policy.project_root
        )

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
        self.last_timed_loop: dict[str, Any] | None = None
        self._timed_stop_event = threading.Event()
        self._timed_thread: threading.Thread | None = None

        self.last_background_loop: dict[str, Any] | None = None
        self._background_stop_event = threading.Event()
        self._background_thread: threading.Thread | None = None

        self.last_goal_generation: dict[str, Any] | None = None
        self._last_goal_generation_at = 0.0
        self._goal_generation_interval = 60.0
        self._minimum_backlog_before_generation = 5

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
        return _AUTONOMOUS_DEV_ORCHESTRATION.handle(
            self,
            command,
            context,
        )


    @staticmethod
    def _is_timed_development_command(
        normalized_command: str,
    ) -> bool:

        development_phrases = (
            "rozwijaj projekt",
            "rozwój projektu",
            "rozwoj projektu",
            "pracuj nad projektem",
            "pracuj autonomicznie",
        )

        return any(
            phrase in normalized_command
            for phrase in development_phrases
        )

    @staticmethod
    def _extract_duration_seconds(
        normalized_command: str,
    ) -> int:

        patterns = (
            (
                r"(\d+)\s*(?:godzin|godziny|godzinę|godzine|h)\b",
                3600,
            ),
            (
                r"(\d+)\s*(?:minut|minuty|minutę|minute|min)\b",
                60,
            ),
            (
                r"(\d+)\s*(?:sekund|sekundy|sekundę|sekunde|s)\b",
                1,
            ),
        )

        for pattern, multiplier in patterns:
            match = re.search(
                pattern,
                normalized_command,
            )

            if match:
                return max(
                    1,
                    int(match.group(1)) * multiplier,
                )

        return 30 * 60

    def start_timed_autonomous_loop(
        self,
        *,
        duration_seconds: int,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        if (
            self._timed_thread is not None
            and self._timed_thread.is_alive()
        ):
            return {
                "success": True,
                "status": "ALREADY_RUNNING",
                "duration_seconds": duration_seconds,
                "last_timed_loop": self.last_timed_loop,
            }

        normalized_context = dict(context or {})
        normalized_context.setdefault(
            "auto_approve",
            True,
        )
        normalized_context.setdefault(
            "auto_execute",
            True,
        )
        normalized_context.setdefault(
            "stop_on_failure",
            True,
        )

        self._timed_stop_event.clear()

        self.last_timed_loop = {
            "success": True,
            "status": "STARTING",
            "duration_seconds": duration_seconds,
            "started_at": time.time(),
            "completed_cycles": 0,
            "attempted_cycles": 0,
            "last_result": None,
        }

        self._timed_thread = threading.Thread(
            target=self._timed_loop_worker,
            kwargs={
                "duration_seconds": max(
                    1,
                    int(duration_seconds),
                ),
                "context": normalized_context,
            },
            name="jarvis-autonomous-dev-loop",
            daemon=True,
        )
        self._timed_thread.start()

        return {
            "success": True,
            "status": "TIMED_LOOP_STARTED",
            "duration_seconds": duration_seconds,
            "auto_approve": bool(
                normalized_context.get(
                    "auto_approve",
                    True,
                )
            ),
            "auto_execute": bool(
                normalized_context.get(
                    "auto_execute",
                    True,
                )
            ),
            "message": (
                "Autonomiczny rozwój projektu "
                "został uruchomiony w tle."
            ),
        }

    def stop_timed_autonomous_loop(
        self,
    ) -> dict[str, Any]:

        running = bool(
            self._timed_thread is not None
            and self._timed_thread.is_alive()
        )

        self._timed_stop_event.set()

        return {
            "success": True,
            "status": (
                "STOP_REQUESTED"
                if running
                else "NOT_RUNNING"
            ),
            "last_timed_loop": self.last_timed_loop,
        }

    def _timed_loop_worker(
        self,
        *,
        duration_seconds: int,
        context: dict[str, Any],
    ) -> None:

        started_at = time.monotonic()
        deadline = started_at + duration_seconds
        attempted_cycles = 0
        completed_cycles = 0
        final_status = "TIME_LIMIT_REACHED"
        last_result: dict[str, Any] | None = None

        try:
            while (
                time.monotonic() < deadline
                and not self._timed_stop_event.is_set()
            ):
                attempted_cycles += 1

                self._maybe_generate_autonomous_goals(
                    context
                )

                last_result = self.run_autonomous_loop(
                    max_cycles=1,
                    context=context,
                    auto_approve=bool(
                        context.get(
                            "auto_approve",
                            True,
                        )
                    ),
                    auto_execute=bool(
                        context.get(
                            "auto_execute",
                            True,
                        )
                    ),
                    stop_on_failure=bool(
                        context.get(
                            "stop_on_failure",
                            True,
                        )
                    ),
                )

                completed_cycles += int(
                    last_result.get(
                        "completed_cycles",
                        0,
                    )
                    or 0
                )

                status = str(
                    last_result.get(
                        "status",
                        "UNKNOWN",
                    )
                ).upper()

                if status in {
                    "GENERATION_FAILED",
                    "EXECUTION_FAILED",
                    "WAITING_FOR_CODE_INPUT",
                    "WAITING_FOR_APPROVAL",
                    "APPROVED_NOT_EXECUTED",
                    "ROLLED_BACK",
                }:
                    final_status = status
                    break

                if status == "NO_TASKS":
                    time.sleep(1.0)
                else:
                    time.sleep(0.2)

            if self._timed_stop_event.is_set():
                final_status = "STOPPED_BY_USER"

        except Exception as error:
            report = AutoDevErrorReporter.capture(
                error,
                stage="autonomous_dev.timed_loop",
                context={
                    "duration_seconds": duration_seconds,
                    "cycles_completed": cycles_completed,
                },
                project_root=self.project_root,
            )
            final_status = "FAILED"
            last_result = {
                "success": False,
                "status": "FAILED",
                "error": report.summary(),
                "error_details": report.as_dict(),
            }

        self.last_timed_loop = {
            "success": final_status not in {
                "FAILED",
                "GENERATION_FAILED",
                "EXECUTION_FAILED",
            },
            "status": final_status,
            "duration_seconds": duration_seconds,
            "elapsed_seconds": round(
                time.monotonic() - started_at,
                3,
            ),
            "attempted_cycles": attempted_cycles,
            "completed_cycles": completed_cycles,
            "last_result": last_result,
            "finished_at": time.time(),
        }

        self._remember_learning(
            success=bool(
                self.last_timed_loop["success"]
            ),
            status=final_status,
            lessons=[
                (
                    "Czasowa pętla autonomiczna "
                    f"wykonała {completed_cycles} cykli."
                )
            ],
            metadata={
                "stage": "timed_autonomous_loop",
                "duration_seconds": duration_seconds,
                "attempted_cycles": attempted_cycles,
            },
        )

    def start_background(
        self,
        *,
        context: dict[str, Any] | None = None,
        interval_seconds: float = 2.0,
    ) -> dict[str, Any]:

        if (
            self._background_thread is not None
            and self._background_thread.is_alive()
        ):
            return {
                "success": True,
                "status": "ALREADY_RUNNING",
                "running": True,
                "last_background_loop": (
                    self.last_background_loop
                ),
            }

        normalized_context = dict(
            context
            or {}
        )
        normalized_context.setdefault(
            "auto_approve",
            True,
        )
        normalized_context.setdefault(
            "auto_execute",
            True,
        )
        normalized_context.setdefault(
            "stop_on_failure",
            False,
        )
        normalized_context.setdefault(
            "source",
            "BrainAutostart",
        )

        safe_interval = max(
            0.5,
            float(interval_seconds),
        )

        self._background_stop_event.clear()

        self.last_background_loop = {
            "success": True,
            "status": "STARTING",
            "running": True,
            "started_at": time.time(),
            "completed_cycles": 0,
            "attempted_cycles": 0,
            "last_result": None,
            "interval_seconds": safe_interval,
        }

        self._background_thread = threading.Thread(
            target=self._background_loop_worker,
            kwargs={
                "context": normalized_context,
                "interval_seconds": safe_interval,
            },
            name="jarvis-background-autodev",
            daemon=True,
        )
        self._background_thread.start()

        return {
            "success": True,
            "status": "BACKGROUND_STARTED",
            "running": True,
            "interval_seconds": safe_interval,
        }

    def stop_background(
        self,
        *,
        wait: bool = False,
        timeout: float = 5.0,
    ) -> dict[str, Any]:

        running = bool(
            self._background_thread is not None
            and self._background_thread.is_alive()
        )

        self._background_stop_event.set()

        if (
            wait
            and self._background_thread is not None
            and self._background_thread.is_alive()
        ):
            self._background_thread.join(
                timeout=max(
                    0.1,
                    float(timeout),
                )
            )

        still_running = bool(
            self._background_thread is not None
            and self._background_thread.is_alive()
        )

        return {
            "success": not still_running,
            "status": (
                "STOPPED"
                if not still_running
                else "STOP_REQUESTED"
            ),
            "running": still_running,
            "was_running": running,
        }

    def _background_loop_worker(
        self,
        *,
        context: dict[str, Any],
        interval_seconds: float,
    ) -> None:

        """Coordinates background loop worker for the JARVIS OS runtime."""
        attempted_cycles = 0
        completed_cycles = 0
        final_status = "STOPPED"
        last_result: dict[str, Any] | None = None

        self.pipeline.start()

        if self._background_stop_event.wait(8.0):
            return

        try:
            while not self._background_stop_event.is_set():
                if (
                    self._timed_thread is not None
                    and self._timed_thread.is_alive()
                ):
                    time.sleep(
                        interval_seconds
                    )
                    continue

                attempted_cycles += 1

                last_result = self.run_autonomous_loop(
                    max_cycles=1,
                    context=context,
                    auto_approve=bool(
                        context.get(
                            "auto_approve",
                            True,
                        )
                    ),
                    auto_execute=bool(
                        context.get(
                            "auto_execute",
                            True,
                        )
                    ),
                    stop_on_failure=bool(
                        context.get(
                            "stop_on_failure",
                            False,
                        )
                    ),
                )

                completed_cycles += int(
                    last_result.get(
                        "completed_cycles",
                        0,
                    )
                    or 0
                )

                final_status = str(
                    last_result.get(
                        "status",
                        "UNKNOWN",
                    )
                ).upper()

                self.last_background_loop = {
                    "success": bool(
                        last_result.get(
                            "success",
                            False,
                        )
                    ),
                    "status": final_status,
                    "running": True,
                    "started_at": (
                        self.last_background_loop
                        or {}
                    ).get(
                        "started_at",
                        time.time(),
                    ),
                    "updated_at": time.time(),
                    "completed_cycles": completed_cycles,
                    "attempted_cycles": attempted_cycles,
                    "last_result": last_result,
                    "interval_seconds": interval_seconds,
                }

                if final_status in {
                    "NO_TASKS",
                    "WAITING_FOR_CODE_INPUT",
                    "WAITING_FOR_APPROVAL",
                    "GENERATION_FAILED",
                    "EXECUTION_FAILED",
                    "FAILED_AND_ROLLED_BACK",
                    "ROLLED_BACK",
                }:
                    time.sleep(
                        interval_seconds
                    )
                else:
                    time.sleep(
                        min(
                            interval_seconds,
                            1.0,
                        )
                    )

        except Exception as error:
            report = AutoDevErrorReporter.capture(
                error,
                stage="autonomous_dev.background_loop",
                context={
                    "cycles_completed": cycles_completed,
                },
                project_root=self.project_root,
            )
            final_status = "FAILED"
            last_result = {
                "success": False,
                "status": "FAILED",
                "error": report.summary(),
                "error_details": report.as_dict(),
            }

        self.last_background_loop = {
            "success": final_status != "FAILED",
            "status": (
                "STOPPED"
                if self._background_stop_event.is_set()
                else final_status
            ),
            "running": False,
            "completed_cycles": completed_cycles,
            "attempted_cycles": attempted_cycles,
            "last_result": last_result,
            "finished_at": time.time(),
            "interval_seconds": interval_seconds,
        }

    def background_status(
        self,
    ) -> dict[str, Any]:

        running = bool(
            self._background_thread is not None
            and self._background_thread.is_alive()
        )

        result = dict(
            self.last_background_loop
            or {}
        )

        result.setdefault(
            "success",
            True,
        )
        result["running"] = running
        result["status"] = (
            "RUNNING"
            if running
            else str(
                result.get(
                    "status",
                    "STOPPED",
                )
            )
        )
        result["pipeline"] = self.pipeline.status()
        result["backlog"] = self.backlog_summary()

        return result

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
        return _AUTONOMOUS_DEV_ORCHESTRATION.run_autonomous_loop(
            self,
            max_cycles=max_cycles,
            context=context,
            auto_approve=auto_approve,
            auto_execute=auto_execute,
            stop_on_failure=stop_on_failure,
        )


    def _collect_execution_errors(
        self,
        execution: dict[str, Any],
    ) -> list[str]:
        return _AUTONOMOUS_DEV_ORCHESTRATION._collect_execution_errors(
            self,
            execution,
        )


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

    def generate_autonomous_goals(
        self,
        *,
        context: dict[str, Any] | None = None,
        limit: int = 10,
    ) -> dict[str, Any]:

        normalized_context = dict(context or {})
        safe_limit = max(1, min(25, int(limit)))

        scan = self.planner.scan_and_plan(
            context_by_module=normalized_context.get(
                "context_by_module"
            )
        )

        planned_items = list(
            scan.get("tasks", []) or []
        )

        created: list[dict[str, Any]] = []
        duplicates: list[dict[str, Any]] = []
        errors: list[str] = []

        for item in planned_items[:safe_limit]:
            task = dict(item or {})
            title = str(
                task.get(
                    "title",
                    task.get(
                        "description",
                        "Autonomiczne ulepszenie projektu",
                    ),
                )
            ).strip()
            description = str(
                task.get(
                    "description",
                    title,
                )
            ).strip()
            target = str(
                task.get(
                    "target",
                    task.get(
                        "module",
                        "",
                    ),
                )
            ).strip()

            try:
                queued = self.submit_goal(
                    goal=description,
                    source="AutonomousProjectPlanner",
                    priority=self.calculate_priority(
                        goal=f"{title} {description}",
                        context={
                            "priority": task.get("priority")
                        },
                    ),
                    context={
                        "target": target,
                        "path": target,
                        "mode": "file",
                        "auto_approve": True,
                        "auto_execute": True,
                        "auto_rollback": True,
                        "tags": [
                            "autonomous-planner",
                            "self-development",
                        ],
                        "metadata": {
                            "planner_task_id": str(
                                task.get("task_id", "")
                            ),
                            "planner_title": title,
                            "planner_generated": True,
                            "severity": str(
                                task.get("severity", "")
                            ),
                        },
                    },
                )
                created.append(queued)
            except ValueError as error:
                duplicates.append({
                    "title": title,
                    "target": target,
                    "reason": str(error),
                })
            except Exception as error:
                report = AutoDevErrorReporter.capture(
                    error,
                    stage=(
                        "autonomous_dev."
                        "generate_autonomous_goals"
                    ),
                    context={
                        "title": title,
                        "target": target,
                    },
                    project_root=self.project_root,
                )
                errors.append(
                    report.summary()
                )
                error_details.append(
                    report.as_dict()
                )

        result = {
            "success": not errors,
            "status": (
                "GOALS_GENERATED"
                if created
                else "NO_NEW_GOALS"
            ),
            "created_count": len(created),
            "duplicate_count": len(duplicates),
            "errors_count": len(errors),
            "created": created,
            "duplicates": duplicates,
            "errors": errors,
            "scan": scan,
            "backlog": self.backlog_summary(),
            "generated_at": time.time(),
        }

        self.last_goal_generation = dict(result)
        self._last_goal_generation_at = time.monotonic()
        return result

    def _maybe_generate_autonomous_goals(
        self,
        context: dict[str, Any],
    ) -> dict[str, Any] | None:

        total = int(
            self.backlog_summary().get(
                "total",
                0,
            )
            or 0
        )

        if total >= self._minimum_backlog_before_generation:
            return None

        if (
            time.monotonic()
            - self._last_goal_generation_at
            < self._goal_generation_interval
        ):
            return None

        return self.generate_autonomous_goals(
            context=context,
            limit=10,
        )

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
            report = AutoDevErrorReporter.capture(
                error,
                stage="autonomous_dev.planning_cycle",
                context={
                    "task_id": task_id,
                    "task_title": task.get(
                        "title",
                        "",
                    ),
                },
                project_root=self.project_root,
            )

            if task_id:
                self.planner.fail_task(
                    task_id,
                    str(error),
                )

            result = {
                "success": False,
                "status": "PLANNING_FAILED",
                "task": task,
                "error": report.summary(),
                "error_details": report.as_dict(),
                "scan": scan_result,
            }

            self.last_planning_cycle = dict(result)
            return result

        proposed = {}
        if isinstance(plan, dict):
            proposed = dict(plan.get("code_proposal") or {})
        status = "READY_FOR_CODE_GENERATION"
        if proposed.get("success"):
            status = "GENERATING_PATCH"

        result = {
            "success": True,
            "status": status,
            "task": task,
            "plan": plan,
            "code_proposal": proposed,
            "proposed_content": proposed.get("proposed_content",""),
            "scan": scan_result,
        }

        self.last_planning_cycle = dict(result)
        return result

    def run_generation_cycle(
        self,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return _AUTONOMOUS_DEV_ORCHESTRATION.run_generation_cycle(
            self,
            context,
        )


    def _prepare_autonomous_code_context(
        self,
        *,
        task: dict[str, Any],
        plan: dict[str, Any],
        context: dict[str, Any],
    ) -> dict[str, Any]:
        return _AUTONOMOUS_DEV_ORCHESTRATION._prepare_autonomous_code_context(
            self,
            task=task,
            plan=plan,
            context=context,
        )


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
            except ValueError as error:
                allowed = ", ".join(
                    str(item.value)
                    for item in TaskPriority
                )
                raise ValueError(
                    "Nieznany priorytet AutoDev: "
                    f"{explicit_priority}. "
                    f"Dozwolone wartości: {allowed}."
                ) from error

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

        pipeline_tasks = self.list_tasks()

        pipeline_by_status: dict[str, int] = {}
        by_priority: dict[str, int] = {}

        for task in pipeline_tasks:
            status = str(
                task.get(
                    "status",
                    "UNKNOWN",
                )
            )
            priority = str(
                task.get(
                    "priority",
                    "UNKNOWN",
                )
            )

            pipeline_by_status[status] = (
                pipeline_by_status.get(
                    status,
                    0,
                )
                + 1
            )
            by_priority[priority] = (
                by_priority.get(
                    priority,
                    0,
                )
                + 1
            )

        planner_summary = dict(
            self.planner.backlog.summary()
            or {}
        )
        planner_by_status = dict(
            planner_summary.get(
                "by_status",
                {},
            )
            or {}
        )

        combined_by_status = dict(
            pipeline_by_status
        )

        for status, count in planner_by_status.items():
            combined_by_status[status] = (
                combined_by_status.get(
                    status,
                    0,
                )
                + int(
                    count
                    or 0
                )
            )

        planner_total = int(
            planner_summary.get(
                "total",
                0,
            )
            or 0
        )
        pipeline_total = len(
            pipeline_tasks
        )

        return {
            "total": (
                pipeline_total
                + planner_total
            ),
            "active": int(
                planner_summary.get(
                    "active",
                    0,
                )
                or 0
            ),
            "pipeline_total": pipeline_total,
            "planner_total": planner_total,
            "by_status": combined_by_status,
            "by_priority": by_priority,
            "next_task": planner_summary.get(
                "next_task"
            ),
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
            "last_timed_loop": self.last_timed_loop,
            "timed_loop_running": bool(
                self._timed_thread is not None
                and self._timed_thread.is_alive()
            ),
            "last_background_loop": (
                self.last_background_loop
            ),
            "last_goal_generation": (
                self.last_goal_generation
            ),
            "background_running": bool(
                self._background_thread is not None
                and self._background_thread.is_alive()
            ),
            "running": bool(
                (
                    self._background_thread is not None
                    and self._background_thread.is_alive()
                )
                or (
                    self._timed_thread is not None
                    and self._timed_thread.is_alive()
                )
            ),
            "status": (
                "RUNNING"
                if (
                    (
                        self._background_thread is not None
                        and self._background_thread.is_alive()
                    )
                    or (
                        self._timed_thread is not None
                        and self._timed_thread.is_alive()
                    )
                )
                else "READY"
            ),
            "learning": self.learning_summary(),
        }
