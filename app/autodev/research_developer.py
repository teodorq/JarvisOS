from app.core.project_paths import (
    default_project_path,
    default_project_root,
)

from pathlib import Path
from typing import Optional

from app.autodev.developer_controller import (
    DeveloperController
)
from app.autodev.developer_request import (
    DeveloperRequest
)
from app.autodev.research_task import (
    ResearchTask
)
from app.autodev.workflow_result import (
    WorkflowResult
)


class ResearchDeveloper:
    """
    Bezpieczny most między Research Agent
    a DeveloperController.

    ResearchTask opisuje problem i cel zmiany.

    DeveloperRequest zawiera konkretny kod,
    który może zostać pokazany w preview,
    zaakceptowany i wykonany.
    """

    def __init__(
        self,
        project_root: str = default_project_root()
    ):
        self.project_root = Path(
            project_root
        ).resolve()

        self.controller = DeveloperController(
            project_root=str(
                self.project_root
            )
        )

        self.current_task: Optional[
            ResearchTask
        ] = None

        self.last_request: Optional[
            DeveloperRequest
        ] = None

        self.last_result: Optional[
            WorkflowResult
        ] = None

    def prepare_file_change(
        self,
        task: ResearchTask,
        proposed_content: str
    ) -> WorkflowResult:

        validation_errors = (
            self._validate_task(
                task
            )
        )

        if validation_errors:
            result = self._failed_result(
                status="invalid_research_task",
                message=(
                    "Zadanie Research Agent "
                    "jest niepoprawne."
                ),
                errors=validation_errors
            )

            self.last_result = result
            return result

        target_path = self._resolve_target(
            task.target
        )

        if not target_path.exists():
            result = self._failed_result(
                status="target_not_found",
                message=(
                    "Nie znaleziono pliku "
                    "wskazanego przez Research Agent."
                ),
                errors=[
                    f"Plik nie istnieje: {target_path}"
                ]
            )

            self.last_result = result
            return result

        if not target_path.is_file():
            result = self._failed_result(
                status="target_not_file",
                message=(
                    "Target ResearchTask "
                    "nie wskazuje pliku."
                ),
                errors=[
                    f"To nie jest plik: {target_path}"
                ]
            )

            self.last_result = result
            return result

        if not proposed_content:
            result = self._failed_result(
                status="missing_proposed_content",
                message=(
                    "Brak proponowanej "
                    "zawartości pliku."
                ),
                errors=[
                    (
                        "ResearchDeveloper wymaga "
                        "pełnej nowej zawartości pliku."
                    )
                ]
            )

            self.last_result = result
            return result

        self.current_task = task

        request = DeveloperRequest(
            goal=self._build_goal(
                task
            ),
            target=str(
                target_path
            ),
            mode="file",
            path=str(
                target_path
            ),
            proposed_content=(
                proposed_content
            ),
            metadata=self._build_metadata(
                task
            )
        )

        self.last_request = request

        result = self.controller.prepare(
            request
        )

        self.last_result = result

        if result.success:
            task.wait_for_approval()

        else:
            task.fail()

        return result

    def prepare_function_change(
        self,
        task: ResearchTask,
        function_name: str,
        new_function_code: str
    ) -> WorkflowResult:

        validation_errors = (
            self._validate_task(
                task
            )
        )

        if validation_errors:
            result = self._failed_result(
                status="invalid_research_task",
                message=(
                    "Zadanie Research Agent "
                    "jest niepoprawne."
                ),
                errors=validation_errors
            )

            self.last_result = result
            return result

        target_path = self._resolve_target(
            task.target
        )

        if not target_path.exists():
            result = self._failed_result(
                status="target_not_found",
                message=(
                    "Nie znaleziono pliku "
                    "wskazanego przez Research Agent."
                ),
                errors=[
                    f"Plik nie istnieje: {target_path}"
                ]
            )

            self.last_result = result
            return result

        if not function_name.strip():
            result = self._failed_result(
                status="missing_function_name",
                message=(
                    "Brak nazwy funkcji "
                    "do zastąpienia."
                ),
                errors=[
                    "function_name jest pusty."
                ]
            )

            self.last_result = result
            return result

        if not new_function_code.strip():
            result = self._failed_result(
                status="missing_function_code",
                message=(
                    "Brak nowego kodu funkcji."
                ),
                errors=[
                    "new_function_code jest pusty."
                ]
            )

            self.last_result = result
            return result

        self.current_task = task

        request = DeveloperRequest(
            goal=self._build_goal(
                task
            ),
            target=str(
                target_path
            ),
            mode="function",
            path=str(
                target_path
            ),
            function_name=(
                function_name
            ),
            new_function_code=(
                new_function_code
            ),
            metadata=self._build_metadata(
                task
            )
        )

        self.last_request = request

        result = self.controller.prepare(
            request
        )

        self.last_result = result

        if result.success:
            task.wait_for_approval()

        else:
            task.fail()

        return result

    def approve(
        self
    ) -> WorkflowResult:

        result = self.controller.approve()

        self.last_result = result

        if (
            result.success
            and self.current_task is not None
        ):
            self.current_task.status = "approved"

        return result

    def execute(
        self,
        auto_rollback: bool = True
    ) -> WorkflowResult:

        if self.current_task is not None:
            self.current_task.start()

        result = self.controller.execute(
            auto_rollback=auto_rollback
        )

        self.last_result = result

        if self.current_task is not None:
            if result.success:
                self.current_task.complete()

            elif result.status == (
                "failed_and_rolled_back"
            ):
                self.current_task.fail()

                self.current_task.metadata[
                    "rolled_back"
                ] = True

            else:
                self.current_task.fail()

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

        result = self.controller.reject(
            reason=reason
        )

        self.last_result = result

        if (
            result.success
            and self.current_task is not None
        ):
            self.current_task.cancel()

            if reason:
                self.current_task.metadata[
                    "rejection_reason"
                ] = reason

        return result

    def rollback_last(
        self
    ) -> WorkflowResult:

        result = (
            self.controller.rollback_last()
        )

        self.last_result = result

        if (
            result.success
            and self.current_task is not None
        ):
            self.current_task.status = (
                "rolled_back"
            )

            self.current_task.metadata[
                "rolled_back"
            ] = True

        return result

    def preview(
        self
    ) -> str:

        return (
            self.controller.current_preview()
        )

    def status(
        self
    ) -> dict:

        controller_status = (
            self.controller.status()
        )

        return {
            "has_task": (
                self.current_task is not None
            ),
            "task_title": (
                self.current_task.title
                if self.current_task
                else ""
            ),
            "task_target": (
                self.current_task.target
                if self.current_task
                else ""
            ),
            "task_status": (
                self.current_task.status
                if self.current_task
                else ""
            ),
            "has_request": (
                self.last_request is not None
            ),
            "has_result": (
                self.last_result is not None
            ),
            **controller_status
        }

    def report(
        self
    ) -> str:

        lines = [
            "RESEARCH DEVELOPER",
            ""
        ]

        if self.current_task is not None:
            lines.append(
                self.current_task.summary()
            )

        else:
            lines.append(
                "Brak aktywnego zadania."
            )

        lines.append("")
        lines.append(
            self.controller.report()
        )

        return "\n".join(
            lines
        )

    def reset(
        self
    ):

        self.controller.reset()

        self.current_task = None
        self.last_request = None
        self.last_result = None

    def _resolve_target(
        self,
        target: str
    ) -> Path:

        target_path = Path(
            target
        )

        if not target_path.is_absolute():
            target_path = (
                self.project_root
                / target_path
            )

        return target_path.resolve()

    def _validate_task(
        self,
        task: ResearchTask
    ) -> list[str]:

        errors = []

        if task is None:
            return [
                "Brak ResearchTask."
            ]

        if not task.title.strip():
            errors.append(
                "ResearchTask nie ma tytułu."
            )

        if not task.target.strip():
            errors.append(
                "ResearchTask nie ma targetu."
            )

        if task.status not in {
            "pending",
            "approved",
            "waiting_for_approval"
        }:
            errors.append(
                "Niepoprawny status zadania: "
                f"{task.status}"
            )

        return errors

    def _build_goal(
        self,
        task: ResearchTask
    ) -> str:

        actions_text = ""

        if task.actions:
            actions_text = (
                " Działania: "
                + "; ".join(
                    task.actions
                )
            )

        return (
            f"{task.title}. "
            f"{task.description}"
            f"{actions_text}"
        ).strip()

    def _build_metadata(
        self,
        task: ResearchTask
    ) -> dict[str, str]:

        metadata = {
            "source": "research_developer",
            "research_task_title": (
                task.title
            ),
            "research_task_type": (
                task.task_type
            ),
            "research_task_priority": str(
                task.priority
            ),
            "estimated_risk": (
                task.estimated_risk
            ),
            "requires_backup": str(
                task.requires_backup
            ),
            "requires_validation": str(
                task.requires_validation
            ),
            "requires_approval": str(
                task.requires_approval
            )
        }

        for key, value in (
            task.metadata.items()
        ):
            metadata[
                f"task_{key}"
            ] = str(
                value
            )

        return metadata

    def _failed_result(
        self,
        status: str,
        message: str,
        errors: list[str]
    ) -> WorkflowResult:

        return WorkflowResult(
            success=False,
            status=status,
            message=message,
            errors=errors
        )