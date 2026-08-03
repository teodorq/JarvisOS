from app.core.project_paths import (
    default_project_path,
    default_project_root,
)

from pathlib import Path
from typing import Any, Iterable, Optional

from app.autodev.autonomous_task_queue import (
    AutonomousTaskQueue,
    DevelopmentGoal,
    TaskPriority,
)
from app.autodev.developer_executor import (
    DeveloperExecutor
)
from app.autodev.execution_guard import (
    ExecutionGuard,
)
from app.autodev.execution_policy import (
    ExecutionPolicy,
)
from app.autodev.developer_request import (
    DeveloperRequest
)
from app.autodev.developer_validator import (
    DeveloperValidator
)
from app.autodev.developer_session import (
    DeveloperSession
)
from app.autodev.patch_generator import (
    PatchGenerator
)
from app.autodev.patch_preview import (
    PatchPreview
)
from app.autodev.transaction_builder import (
    TransactionBuilder
)
from app.autodev.workflow_result import (
    WorkflowResult
)
from app.autodev.developer_controller_workflow_service import (
    DeveloperControllerWorkflowService,
)


_DEVELOPER_CONTROLLER_WORKFLOW = DeveloperControllerWorkflowService()


class DeveloperController:

    def __init__(
        self,
        project_root: str | Path | None = None,
        task_queue: AutonomousTaskQueue | None = None,
        execution_guard: ExecutionGuard | None = None,
    ):
        self.project_root = Path(
            project_root
            or default_project_root()
        ).expanduser().resolve(
            strict=False
        )

        self.patch_generator = (
            PatchGenerator()
        )

        self.transaction_builder = (
            TransactionBuilder()
        )

        self.patch_preview = (
            PatchPreview()
        )

        tests_available = (
            self.project_root
            / "tests"
        ).is_dir()

        self.executor = DeveloperExecutor(
            project_root=str(
                self.project_root
            ),
            run_tests=tests_available,
            full_test_suite=tests_available,
        )

        self.validator = DeveloperValidator(
            project_root=str(
                self.project_root
            )
        )

        self.execution_guard = (
            execution_guard
            or ExecutionGuard(
                policy=ExecutionPolicy(
                    project_root=self.project_root,
                    allow_auto_approval=True,
                    max_auto_approval_risk=20.0,
                )
            )
        )

        self.session = DeveloperSession()

        self.task_queue = task_queue

        self.last_request: Optional[
            DeveloperRequest
        ] = None

        self.last_result: Optional[
            WorkflowResult
        ] = None

    def register_goal(
        self,
        title: str,
        description: str,
        *,
        priority: TaskPriority = TaskPriority.NORMAL,
        tags: Iterable[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> DevelopmentGoal:
        if self.task_queue is None:
            raise RuntimeError(
                "DeveloperController nie ma przypisanej kolejki zadań."
            )

        return self.task_queue.create_goal(
            title=title,
            description=description,
            priority=priority,
            tags=tags,
            metadata=metadata,
        )

    def add_goal_task(
        self,
        goal_id: str,
        *,
        title: str,
        description: str,
        source: str = "developer_controller",
        priority: TaskPriority | None = None,
        payload: dict[str, Any] | None = None,
        tags: Iterable[str] | None = None,
        dependencies: Iterable[str] | None = None,
    ):
        if self.task_queue is None:
            raise RuntimeError(
                "DeveloperController nie ma przypisanej kolejki zadań."
            )

        goal = self.task_queue.require_goal(goal_id)
        task = self.task_queue.create_task(
            title=title,
            description=description,
            source=source,
            priority=priority or goal.priority,
            payload={
                **dict(payload or {}),
                "goal_id": goal_id,
            },
            tags=list(tags or goal.tags),
            dependencies=dependencies,
        )
        self.task_queue.add_task_to_goal(goal_id, task.task_id)
        return task

    def goal_status(self, goal_id: str) -> dict[str, Any]:
        if self.task_queue is None:
            raise RuntimeError(
                "DeveloperController nie ma przypisanej kolejki zadań."
            )
        return self.task_queue.goal_progress(goal_id)

    def enqueue_director_plan(
        self,
        objective: str,
        plan: dict[str, Any],
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        return _DEVELOPER_CONTROLLER_WORKFLOW.enqueue_director_plan(
            self,
            objective,
            plan,
            context,
        )


    def _director_plan_items(
        self,
        plan: dict[str, Any],
    ) -> list[dict[str, Any]]:
        decomposition = plan.get(
            "decomposition",
            {}
        )

        if isinstance(decomposition, dict):
            subgoals = decomposition.get(
                "subgoals",
                [],
            )
            if isinstance(subgoals, list):
                normalized = [
                    dict(item)
                    for item in subgoals
                    if isinstance(item, dict)
                ]
                if normalized:
                    return normalized

        steps = plan.get(
            "steps",
            [],
        )

        if not isinstance(steps, list):
            return []

        result: list[dict[str, Any]] = []
        previous_step_id: str | None = None

        for index, step in enumerate(
            steps,
            start=1,
        ):
            step_id = f"step_{index}"

            if isinstance(step, dict):
                item = dict(step)
            else:
                item = {
                    "title": str(step),
                    "description": str(step),
                }

            item.setdefault("step_id", step_id)
            item.setdefault("order", index)
            item.setdefault(
                "dependencies",
                [previous_step_id]
                if previous_step_id
                else [],
            )

            result.append(item)
            previous_step_id = step_id

        return result

    def _director_priority(
        self,
        value: Any,
    ) -> TaskPriority:
        if isinstance(value, TaskPriority):
            return value

        if isinstance(value, int):
            try:
                return TaskPriority(value)
            except ValueError:
                return TaskPriority.NORMAL

        normalized = str(value).strip().upper()

        aliases = {
            "CRITICAL": TaskPriority.CRITICAL,
            "HIGH": TaskPriority.HIGH,
            "MEDIUM": TaskPriority.NORMAL,
            "NORMAL": TaskPriority.NORMAL,
            "LOW": TaskPriority.LOW,
            "BACKGROUND": TaskPriority.BACKGROUND,
        }

        return aliases.get(
            normalized,
            TaskPriority.NORMAL,
        )

    def prepare(
        self,
        request: DeveloperRequest,
    ) -> WorkflowResult:
        return _DEVELOPER_CONTROLLER_WORKFLOW.prepare(
            self,
            request,
        )



    def run(
        self,
        request: DeveloperRequest,
        *,
        auto_approve: bool = False,
        auto_rollback: bool = True
    ) -> WorkflowResult:
        """
        Uruchamia pełny przepływ kontrolera.

        Domyślnie zatrzymuje się na podglądzie i czeka
        na akceptację. W trybie autonomicznym może od razu
        zatwierdzić i wykonać przygotowaną transakcję.
        """
        prepared = self.prepare(
            request
        )

        if not prepared.success:
            return prepared

        if not auto_approve:
            return prepared

        return self.approve_and_execute(
            auto_rollback=auto_rollback,
            automatic_approval=True,
        )

    def approve(
        self,
        *,
        automatic: bool = False,
    ) -> WorkflowResult:

        if not self.session.has_transaction():
            result = WorkflowResult(
                success=False,
                status="nothing_to_approve",
                message=(
                    "Brak przygotowanej "
                    "transakcji do zatwierdzenia."
                ),
                errors=[
                    "Najpierw wykonaj prepare()."
                ]
            )

            self.last_result = result
            return result

        if self.session.status != (
            "waiting_for_approval"
        ):
            result = WorkflowResult(
                success=False,
                status="approval_not_available",
                message=(
                    "Aktualny stan sesji "
                    "nie pozwala na akceptację."
                ),
                transaction=self.session.transaction,
                errors=[
                    (
                        "Status sesji: "
                        f"{self.session.status}"
                    )
                ]
            )

            self.last_result = result
            return result

        guard_decision = self._evaluate_execution_policy(
            automatic=automatic
        )

        if not guard_decision.allowed:
            result = WorkflowResult(
                success=False,
                status=(
                    "automatic_approval_blocked"
                    if automatic
                    else "approval_blocked"
                ),
                message=(
                    "Polityka bezpieczeństwa zablokowała "
                    "zatwierdzenie transakcji."
                ),
                transaction=self.session.transaction,
                errors=list(
                    guard_decision.errors
                    or guard_decision.reasons
                ),
                data={
                    "execution_guard": (
                        guard_decision.to_dict()
                    )
                },
            )
            self.last_result = result
            return result

        approved = self.session.approve()

        if not approved:
            result = WorkflowResult(
                success=False,
                status="approval_failed",
                message=(
                    "Nie udało się zatwierdzić "
                    "transakcji."
                ),
                errors=[
                    "DeveloperSession odrzuciła akceptację."
                ]
            )

            self.last_result = result
            return result

        result = WorkflowResult(
            success=True,
            status="approved",
            message=(
                "Transakcja została "
                "zatwierdzona."
            ),
            transaction=self.session.transaction,
            data={
                "can_execute": (
                    self.session.can_execute()
                )
            }
        )

        self.last_result = result
        return result

    def execute(
        self,
        *,
        auto_rollback: bool = True,
    ) -> WorkflowResult:
        return _DEVELOPER_CONTROLLER_WORKFLOW.execute(
            self,
            auto_rollback=auto_rollback,
        )


    def approve_and_execute(
        self,
        auto_rollback: bool = True,
        *,
        automatic_approval: bool = False,
    ) -> WorkflowResult:

        approval_result = self.approve(
            automatic=automatic_approval
        )

        if not approval_result.success:
            return approval_result

        return self.execute(
            auto_rollback=auto_rollback
        )

    def reject(
        self,
        reason: str = ""
    ) -> WorkflowResult:

        transaction = self.session.transaction

        if transaction is None:
            result = WorkflowResult(
                success=False,
                status="nothing_to_reject",
                message=(
                    "Brak transakcji "
                    "do odrzucenia."
                ),
                errors=[
                    "Nie przygotowano patcha."
                ]
            )

            self.last_result = result
            return result

        if reason:
            self.session.add_note(
                f"Odrzucono: {reason}"
            )

        self.session.cancel()

        result = WorkflowResult(
            success=True,
            status="rejected",
            message=(
                "Patch został odrzucony. "
                "Żaden plik nie został zmieniony."
            ),
            transaction=transaction,
            data={
                "reason": reason
            }
        )

        self.last_result = result
        return result

    def rollback_last(
        self
    ) -> WorkflowResult:

        rollback_result = (
            self.executor.rollback_last()
        )

        transaction = (
            self.executor.last_transaction
        )

        if rollback_result.success:
            self.session.mark_rolled_back()

            result = WorkflowResult(
                success=True,
                status="rolled_back",
                message=(
                    "Ostatnia transakcja "
                    "została cofnięta."
                ),
                transaction=transaction,
                execution_result=rollback_result
            )

            self.last_result = result
            return result

        self.session.mark_failed(
            rollback_result.message
        )

        result = WorkflowResult(
            success=False,
            status="rollback_failed",
            message=(
                "Nie udało się cofnąć "
                "ostatniej transakcji."
            ),
            transaction=transaction,
            execution_result=rollback_result,
            errors=rollback_result.errors
        )

        self.last_result = result
        return result

    def _evaluate_execution_policy(
        self,
        *,
        automatic: bool,
    ):
        return self.execution_guard.evaluate_transaction(
            self.session.transaction,
            approved=True,
            automatic=automatic,
        )

    def current_preview(
        self
    ) -> str:

        transaction = self.session.transaction

        if transaction is None:
            return (
                "Brak aktywnej transakcji "
                "do pokazania."
            )

        return self.patch_preview.build(
            transaction
        )

    def status(
        self
    ) -> dict:

        transaction = self.session.transaction

        return {
            "session_status": (
                self.session.status
            ),
            "approved": (
                self.session.approved
            ),
            "has_transaction": (
                transaction is not None
            ),
            "transaction_status": (
                transaction.status
                if transaction
                else ""
            ),
            "goal": self.session.goal,
            "target": self.session.target,
            "can_execute": (
                self.session.can_execute()
            ),
            "project_root": str(
                self.project_root
            ),
            "execution_guard": (
                self.execution_guard.status()
            ),
            "files_count": (
                len(transaction.changes)
                if transaction
                else 0
            ),
            "notes_count": len(
                self.session.notes
            ),
            "last_result_status": (
                self.last_result.status
                if self.last_result
                else ""
            ),
            "last_result_success": (
                self.last_result.success
                if self.last_result
                else None
            )
        }


    def health(
        self
    ) -> dict:
        checks = {
            "project_root_exists": (
                self.project_root.exists()
            ),
            "project_root_is_directory": (
                self.project_root.is_dir()
            ),
            "patch_generator": (
                self.patch_generator is not None
            ),
            "transaction_builder": (
                self.transaction_builder is not None
            ),
            "patch_preview": (
                self.patch_preview is not None
            ),
            "executor": (
                self.executor is not None
            ),
            "session": (
                self.session is not None
            ),
            "task_queue_valid": (
                self.task_queue is None
                or isinstance(self.task_queue, AutonomousTaskQueue)
            )
        }

        healthy = all(
            checks.values()
        )

        return {
            "healthy": healthy,
            "status": (
                "healthy"
                if healthy
                else "degraded"
            ),
            "checks": checks,
            "controller": self.status()
        }

    def report(
        self
    ) -> str:

        lines = [
            "AUTODEV DEVELOPER CONTROLLER",
            "",
            self.session.summary()
        ]

        if self.last_request is not None:
            lines.append("")
            lines.append(
                self.last_request.summary()
            )

        if self.last_result is not None:
            lines.append("")
            lines.append(
                self.last_result.summary()
            )

        return "\n".join(lines)

    def reset(
        self
    ):
        current_task_queue = self.task_queue

        self.session = DeveloperSession()
        self.task_queue = current_task_queue
        self.last_request = None
        self.last_result = None

    def _build_transaction(
        self,
        request: DeveloperRequest,
    ):
        if request.mode == "file":
            return (
                self.patch_generator
                .build_file_patch(
                    goal=request.goal,
                    target=request.target,
                    path=request.path,
                    proposed_content=(
                        request.proposed_content
                    )
                )
            )

        if request.mode == "function":
            return (
                self.patch_generator
                .build_function_patch(
                    goal=request.goal,
                    target=request.target,
                    path=request.path,
                    function_name=(
                        request.function_name
                    ),
                    new_function_code=(
                        request.new_function_code
                    )
                )
            )

        if request.mode == "multi_file":
            raw_allow_create = (
                request.metadata.get(
                    "allow_create",
                    False,
                )
            )
            allow_create = (
                raw_allow_create is True
                or str(
                    raw_allow_create
                ).strip().casefold()
                in {
                    "1",
                    "true",
                    "yes",
                    "tak",
                }
            )
            transaction = (
                self.transaction_builder
                .build_multi_file_replacement(
                    goal=request.goal,
                    target=request.target,
                    replacements=(
                        request.replacements
                    ),
                    allow_create=allow_create,
                )
            )

            return transaction, []

        return (
            None,
            [
                (
                    "Nieobsługiwany tryb "
                    f"żądania: {request.mode}"
                )
            ]
        )
