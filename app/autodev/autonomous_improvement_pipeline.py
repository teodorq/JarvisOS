from __future__ import annotations

from app.core.project_paths import (
    default_project_path,
    default_project_root,
)

from dataclasses import asdict, dataclass
from typing import Any

from app.autodev.code_improvement_workflow import (
    CodeImprovementWorkflow,
)
from app.autodev.improvement_memory import (
    ImprovementMemory,
)
from app.autodev.safe_patch_builder import (
    SafePatchBuilder,
)
from app.autodev.safe_patch_executor import (
    SafePatchExecutionPolicy,
    SafePatchExecutor,
)
from app.autodev.safe_patch_validator import (
    SafePatchValidator,
)


@dataclass(slots=True)
class AutonomousImprovementPolicy:
    project_root: str = default_project_root()
    dry_run: bool = True
    require_approval: bool = True
    run_py_compile: bool = True
    run_unit_tests: bool = True
    auto_rollback: bool = True
    max_changed_lines: int = 500
    memory_path: str = (
        default_project_path("data", "autodev") + "/"
        "improvement_memory.json"
    )


class AutonomousImprovementPipeline:
    """
    Łączy:
    - analizę projektu,
    - wybór celu,
    - generowanie kandydata,
    - budowanie patcha,
    - walidację,
    - dry-run lub wykonanie,
    - pamięć wyników.

    Domyślnie działa w trybie dry-run.
    """

    def __init__(
        self,
        policy: AutonomousImprovementPolicy | None = None,
        workflow: CodeImprovementWorkflow | None = None,
        builder: SafePatchBuilder | None = None,
        validator: SafePatchValidator | None = None,
        executor: SafePatchExecutor | None = None,
        memory: ImprovementMemory | None = None,
    ) -> None:

        self.policy = (
            policy
            or AutonomousImprovementPolicy()
        )

        self.workflow = (
            workflow
            or CodeImprovementWorkflow(
                project_root=self.policy.project_root
            )
        )

        self.builder = (
            builder
            or SafePatchBuilder(
                project_root=self.policy.project_root,
                max_changed_lines=(
                    self.policy.max_changed_lines
                ),
            )
        )

        self.validator = (
            validator
            or SafePatchValidator(
                project_root=self.policy.project_root,
                max_changed_lines=(
                    self.policy.max_changed_lines
                ),
            )
        )

        self.executor = (
            executor
            or SafePatchExecutor(
                policy=SafePatchExecutionPolicy(
                    project_root=(
                        self.policy.project_root
                    ),
                    dry_run=self.policy.dry_run,
                    require_approval=(
                        self.policy.require_approval
                    ),
                    run_py_compile=(
                        self.policy.run_py_compile
                    ),
                    run_unit_tests=(
                        self.policy.run_unit_tests
                    ),
                    auto_rollback=(
                        self.policy.auto_rollback
                    ),
                ),
                validator=self.validator,
            )
        )

        self.memory = (
            memory
            or ImprovementMemory(
                storage_path=self.policy.memory_path
            )
        )

        self.last_result: dict[str, Any] | None = None

    def run(
        self,
        tasks: list[dict[str, Any]],
        *,
        approved: bool = False,
    ) -> dict[str, Any]:

        if not isinstance(
            tasks,
            list,
        ):
            return self._finish(
                {
                    "success": False,
                    "status": "INVALID_TASKS",
                    "error": (
                        "tasks musi być listą."
                    ),
                },
                task={},
                lessons=[
                    "Odrzucono niepoprawny format zadań."
                ],
            )

        workflow_result = self.workflow.run(
            tasks
        )

        if not isinstance(
            workflow_result,
            dict,
        ):
            return self._finish(
                {
                    "success": False,
                    "status": "INVALID_WORKFLOW_RESULT",
                    "workflow": {},
                },
                task={},
                lessons=[
                    "Workflow zwrócił niepoprawny wynik."
                ],
            )

        selected_task = dict(
            workflow_result.get(
                "selected_task"
            )
            or {}
        )

        if workflow_result.get(
            "status"
        ) == "NO_TASKS":
            return self._finish(
                {
                    "success": True,
                    "status": "NO_TASKS",
                    "workflow": workflow_result,
                },
                task=selected_task,
                workflow=workflow_result,
                lessons=[
                    "Brak zadań do przetworzenia."
                ],
            )

        candidate = workflow_result.get(
            "candidate"
        )

        if not isinstance(
            candidate,
            dict,
        ):
            return self._finish(
                {
                    "success": False,
                    "status": "NO_CANDIDATE",
                    "workflow": workflow_result,
                    "error": (
                        "Workflow nie przygotował "
                        "kandydata zmiany."
                    ),
                },
                task=selected_task,
                workflow=workflow_result,
                lessons=[
                    "Nie utworzono kandydata patcha."
                ],
            )

        candidate_success = bool(
            candidate.get(
                "success",
                False,
            )
        )

        if not candidate_success:
            return self._finish(
                {
                    "success": False,
                    "status": str(
                        candidate.get(
                            "status",
                            "CANDIDATE_FAILED",
                        )
                    ),
                    "workflow": workflow_result,
                    "candidate": candidate,
                    "errors": list(
                        candidate.get(
                            "errors",
                            [],
                        )
                    ),
                },
                task=selected_task,
                workflow=workflow_result,
                lessons=[
                    "Generator nie przygotował "
                    "bezpiecznej zmiany."
                ],
            )

        path = str(
            candidate.get(
                "path",
                "",
            )
        ).strip()

        proposed_content = str(
            candidate.get(
                "proposed_content",
                "",
            )
        )

        goal = str(
            candidate.get(
                "goal",
                "",
            )
        ).strip()

        try:
            patch = self.builder.build(
                path=path,
                new_content=proposed_content,
                goal=goal,
                metadata={
                    "source": (
                        "AutonomousImprovementPipeline"
                    ),
                    "workflow_status": str(
                        workflow_result.get(
                            "status",
                            "",
                        )
                    ),
                },
            )

        except Exception as error:
            return self._finish(
                {
                    "success": False,
                    "status": "PATCH_BUILD_FAILED",
                    "workflow": workflow_result,
                    "candidate": candidate,
                    "error": (
                        f"{type(error).__name__}: "
                        f"{error}"
                    ),
                },
                task=selected_task,
                workflow=workflow_result,
                lessons=[
                    "Nie udało się zbudować patcha."
                ],
            )

        validation = self.validator.validate(
            patch
        )

        if not validation.success:
            return self._finish(
                {
                    "success": False,
                    "status": "PATCH_REJECTED",
                    "workflow": workflow_result,
                    "candidate": candidate,
                    "patch": patch.to_dict(),
                    "validation": validation.to_dict(),
                },
                task=selected_task,
                workflow=workflow_result,
                patch=patch.to_dict(),
                validation=validation.to_dict(),
                lessons=[
                    "Walidator odrzucił patch."
                ],
            )

        execution = self.executor.execute(
            patch,
            approved=approved,
        )

        result = {
            "success": execution.success,
            "status": execution.status,
            "workflow": workflow_result,
            "candidate": candidate,
            "patch": patch.to_dict(),
            "validation": validation.to_dict(),
            "execution": execution.to_dict(),
            "dry_run": self.policy.dry_run,
            "approved": approved,
        }

        lessons = self._build_lessons(
            result
        )

        return self._finish(
            result,
            task=selected_task,
            workflow=workflow_result,
            patch=patch.to_dict(),
            validation=validation.to_dict(),
            execution=execution.to_dict(),
            lessons=lessons,
        )

    def _build_lessons(
        self,
        result: dict[str, Any],
    ) -> list[str]:

        status = str(
            result.get(
                "status",
                "UNKNOWN",
            )
        )

        if status == "DRY_RUN_OK":
            return [
                (
                    "Patch przeszedł walidację "
                    "bez zapisu do projektu."
                )
            ]

        if status == "WAITING_FOR_APPROVAL":
            return [
                (
                    "Patch jest poprawny i czeka "
                    "na akceptację."
                )
            ]

        if status == "COMPLETED":
            return [
                (
                    "Patch zapisano, skompilowano "
                    "i przetestowano."
                )
            ]

        if status == "FAILED_AND_ROLLED_BACK":
            return [
                (
                    "Zmiana nie przeszła walidacji "
                    "końcowej i została cofnięta."
                )
            ]

        return [
            f"Pipeline zakończył się statusem {status}."
        ]

    def _finish(
        self,
        result: dict[str, Any],
        *,
        task: dict[str, Any],
        workflow: dict[str, Any] | None = None,
        patch: dict[str, Any] | None = None,
        validation: dict[str, Any] | None = None,
        execution: dict[str, Any] | None = None,
        lessons: list[str] | None = None,
    ) -> dict[str, Any]:

        normalized = dict(
            result
        )

        self.last_result = normalized

        try:
            self.memory.remember(
                success=bool(
                    normalized.get(
                        "success",
                        False,
                    )
                ),
                status=str(
                    normalized.get(
                        "status",
                        "UNKNOWN",
                    )
                ),
                task=task,
                workflow=workflow,
                patch=patch,
                validation=validation,
                execution=execution,
                lessons=lessons,
            )
        except Exception as error:
            normalized[
                "memory_warning"
            ] = (
                f"{type(error).__name__}: {error}"
            )

        return normalized

    def status(
        self,
    ) -> dict[str, Any]:

        return {
            "policy": asdict(
                self.policy
            ),
            "last_result": self.last_result,
            "workflow": self.workflow.status(),
            "builder": self.builder.status(),
            "validator": self.validator.status(),
            "executor": self.executor.status(),
            "memory": self.memory.summary(),
        }
