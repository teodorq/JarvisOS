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
from app.autodev.developer_request import (
    DeveloperRequest
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


class DeveloperController:

    def __init__(
        self,
        project_root: str = "C:/JarvisAI",
        task_queue: AutonomousTaskQueue | None = None
    ):
        self.project_root = Path(
            project_root
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

        self.executor = DeveloperExecutor(
            project_root=project_root
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
        if self.task_queue is None:
            return {
                "success": False,
                "status": "TASK_QUEUE_UNAVAILABLE",
            }

        normalized_objective = str(objective).strip()
        if not normalized_objective:
            return {
                "success": False,
                "status": "EMPTY_OBJECTIVE",
            }

        normalized_plan = (
            dict(plan)
            if isinstance(plan, dict)
            else {}
        )
        normalized_context = (
            dict(context)
            if isinstance(context, dict)
            else {}
        )

        priority = self._director_priority(
            normalized_plan.get("priority")
        )

        goal = self.register_goal(
            title=normalized_objective,
            description=normalized_objective,
            priority=priority,
            tags=[
                "project-director",
                "autodev",
            ],
            metadata={
                "director_plan_id": normalized_plan.get(
                    "plan_id",
                    "",
                ),
                "selected_module": normalized_plan.get(
                    "selected_module",
                    "",
                ),
                "mode": normalized_plan.get(
                    "mode",
                    "",
                ),
                "context": normalized_context,
            },
        )

        items = self._director_plan_items(
            normalized_plan
        )

        task_ids: list[str] = []
        proposal_to_task: dict[str, str] = {}

        for index, item in enumerate(items, start=1):
            proposal_id = str(
                item.get(
                    "proposal_id",
                    item.get("step_id", index),
                )
            )

            dependency_ids = [
                proposal_to_task[dependency]
                for dependency in item.get(
                    "dependencies",
                    [],
                )
                if dependency in proposal_to_task
            ]

            task = self.add_goal_task(
                goal.goal_id,
                title=str(
                    item.get(
                        "title",
                        f"Etap {index}: {normalized_objective}",
                    )
                ).strip(),
                description=str(
                    item.get(
                        "description",
                        item.get(
                            "instruction",
                            normalized_objective,
                        ),
                    )
                ).strip(),
                source="project_director",
                priority=self._director_priority(
                    item.get(
                        "priority",
                        priority,
                    )
                ),
                payload={
                    "director_plan_id": normalized_plan.get(
                        "plan_id",
                        "",
                    ),
                    "director_step": item,
                    "objective": normalized_objective,
                    "order": item.get("order", index),
                },
                tags=[
                    "project-director",
                    "autodev",
                    str(
                        item.get(
                            "subgoal_type",
                            "step",
                        )
                    ).lower(),
                ],
                dependencies=dependency_ids,
            )

            proposal_to_task[proposal_id] = task.task_id
            task_ids.append(task.task_id)

        return {
            "success": True,
            "status": "QUEUED",
            "goal_id": goal.goal_id,
            "task_ids": task_ids,
            "tasks_count": len(task_ids),
            "progress": self.goal_status(
                goal.goal_id
            ),
        }

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
        request: DeveloperRequest
    ) -> WorkflowResult:

        if not isinstance(
            request,
            DeveloperRequest
        ):
            result = WorkflowResult(
                success=False,
                status="request_type_invalid",
                message=(
                    "Przekazano niepoprawny typ "
                    "żądania developerskiego."
                ),
                errors=[
                    "Wymagany obiekt DeveloperRequest."
                ]
            )

            self.last_result = result
            return result

        if self.session.status == "executing":
            result = WorkflowResult(
                success=False,
                status="controller_busy",
                message=(
                    "Kontroler wykonuje już inną "
                    "transakcję."
                ),
                errors=[
                    "Poczekaj na zakończenie aktywnej sesji."
                ]
            )

            self.last_result = result
            return result

        self.last_request = request

        request_valid, request_errors = (
            request.validate()
        )

        if not request_valid:
            result = WorkflowResult(
                success=False,
                status="request_invalid",
                message=(
                    "Żądanie developerskie "
                    "jest niepoprawne."
                ),
                errors=request_errors
            )

            self.last_result = result
            return result

        self.session.start(
            goal=request.goal,
            target=request.target
        )

        try:
            transaction, errors = (
                self._build_transaction(
                    request
                )
            )

        except Exception as error:
            self.session.mark_failed(
                str(error)
            )

            result = WorkflowResult(
                success=False,
                status="prepare_failed",
                message=(
                    "Nie udało się przygotować "
                    "transakcji zmian."
                ),
                errors=[
                    str(error)
                ]
            )

            self.last_result = result
            return result

        if transaction is None:
            self.session.mark_failed(
                "Generator nie utworzył transakcji."
            )

            result = WorkflowResult(
                success=False,
                status="patch_generation_failed",
                message=(
                    "Nie udało się wygenerować "
                    "patcha."
                ),
                errors=errors
            )

            self.last_result = result
            return result

        transaction_valid, transaction_errors = (
            transaction.validate()
        )

        if not transaction_valid:
            transaction.mark_failed()

            for error in transaction_errors:
                self.session.add_note(
                    error
                )

            self.session.mark_failed(
                "Transakcja nie przeszła walidacji."
            )

            result = WorkflowResult(
                success=False,
                status="transaction_invalid",
                message=(
                    "Wygenerowana transakcja "
                    "jest niepoprawna."
                ),
                transaction=transaction,
                errors=transaction_errors
            )

            self.last_result = result
            return result

        if request.metadata:
            transaction.metadata.update(
                request.metadata
            )

        transaction.metadata[
            "request_mode"
        ] = request.mode
        transaction.metadata[
            "project_root"
        ] = str(self.project_root)

        self.session.set_transaction(
            transaction
        )

        preview = self.patch_preview.build(
            transaction
        )

        result = WorkflowResult(
            success=True,
            status="waiting_for_approval",
            message=(
                "Patch został przygotowany. "
                "Wymagana jest akceptacja."
            ),
            preview=preview,
            transaction=transaction,
            data={
                "goal": request.goal,
                "target": request.target,
                "mode": request.mode,
                "files": transaction.files(),
                "files_count": len(
                    transaction.changes
                )
            }
        )

        self.last_result = result
        return result


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
            auto_rollback=auto_rollback
        )

    def approve(
        self
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
        auto_rollback: bool = True
    ) -> WorkflowResult:

        if not self.session.can_execute():
            result = WorkflowResult(
                success=False,
                status="execution_blocked",
                message=(
                    "Transakcja nie została "
                    "zatwierdzona."
                ),
                transaction=self.session.transaction,
                errors=[
                    (
                        "Wymagany status sesji: "
                        "approved."
                    ),
                    (
                        "Aktualny status sesji: "
                        f"{self.session.status}"
                    )
                ]
            )

            self.last_result = result
            return result

        transaction = self.session.transaction

        if transaction is None:
            result = WorkflowResult(
                success=False,
                status="missing_transaction",
                message=(
                    "Brak transakcji "
                    "do wykonania."
                ),
                errors=[
                    "DeveloperSession nie posiada transakcji."
                ]
            )

            self.last_result = result
            return result

        self.session.mark_executing()

        try:
            execution_result = (
                self.executor.execute(
                    transaction=transaction,
                    auto_rollback=auto_rollback
                )
            )

        except Exception as error:
            self.session.mark_failed(
                str(error)
            )

            result = WorkflowResult(
                success=False,
                status="execution_exception",
                message=(
                    "Wystąpił wyjątek podczas "
                    "wykonywania zmian."
                ),
                transaction=transaction,
                errors=[
                    str(error)
                ]
            )

            self.last_result = result
            return result

        if execution_result.success:
            self.session.mark_completed()

            result = WorkflowResult(
                success=True,
                status="completed",
                message=(
                    "Workflow AutoDev został "
                    "zakończony powodzeniem."
                ),
                transaction=transaction,
                execution_result=execution_result,
                data={
                    "changed_files": (
                        transaction.files()
                    ),
                    "backup_bundle": (
                        transaction.backup_bundle_path
                    ),
                    "rollback_used": False
                }
            )

            self.last_result = result
            return result

        execution_data = (
            execution_result.data
            if isinstance(
                execution_result.data,
                dict
            )
            else {}
        )

        rollback_data = execution_data.get(
            "rollback",
            {}
        )

        rollback_success = (
            rollback_data.get(
                "success",
                False
            )
            if isinstance(
                rollback_data,
                dict
            )
            else False
        )

        if rollback_success:
            self.session.mark_rolled_back()

            status = (
                "failed_and_rolled_back"
            )

            message = (
                "Walidacja lub zapis zmian "
                "nie powiodły się. "
                "Pliki zostały przywrócone."
            )

        else:
            self.session.mark_failed(
                execution_result.message
            )

            status = "failed"

            message = (
                "Workflow AutoDev "
                "nie powiódł się."
            )

        result = WorkflowResult(
            success=False,
            status=status,
            message=message,
            transaction=transaction,
            execution_result=execution_result,
            errors=execution_result.errors,
            data={
                "rollback_attempted": (
                    bool(rollback_data)
                ),
                "rollback_success": (
                    rollback_success
                ),
                "backup_bundle": (
                    transaction.backup_bundle_path
                )
            }
        )

        self.last_result = result
        return result

    def approve_and_execute(
        self,
        auto_rollback: bool = True
    ) -> WorkflowResult:

        approval_result = self.approve()

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
        self.session = DeveloperSession()

        self.task_queue = task_queue
        self.last_request = None
        self.last_result = None

    def _build_transaction(
        self,
        request: DeveloperRequest
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
            transaction = (
                self.transaction_builder
                .build_multi_file_replacement(
                    goal=request.goal,
                    target=request.target,
                    replacements=(
                        request.replacements
                    )
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