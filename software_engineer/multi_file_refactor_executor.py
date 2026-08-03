from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.autodev.developer_controller import (
    DeveloperController,
)
from app.autodev.developer_request import (
    DeveloperRequest,
)

from .refactor_models import (
    MultiFileRefactorPlan,
)


@dataclass(frozen=True, slots=True)
class MultiFileRefactorPolicy:
    max_files: int = 12
    max_risk_score: float = 85.0

    def __post_init__(self) -> None:
        if self.max_files < 2:
            raise ValueError(
                "max_files musi wynosić co najmniej 2."
            )

        if (
            self.max_risk_score <= 0
            or self.max_risk_score > 100
        ):
            raise ValueError(
                "max_risk_score musi mieścić się w zakresie 0..100."
            )


class MultiFileRefactorExecutor:
    """Executes an approved refactor plan as one update transaction."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        developer_controller: DeveloperController | None = None,
        policy: MultiFileRefactorPolicy | None = None,
    ) -> None:
        self.project_root = Path(
            project_root
        ).expanduser().resolve(
            strict=False
        )
        self.developer_controller = (
            developer_controller
            or DeveloperController(
                project_root=self.project_root
            )
        )
        self.policy = (
            policy
            or MultiFileRefactorPolicy()
        )

    def execute(
        self,
        plan: MultiFileRefactorPlan,
        *,
        auto_approve: bool = False,
        auto_rollback: bool = True,
    ) -> dict[str, Any]:
        validation_errors = self._validate_plan(
            plan
        )

        if validation_errors:
            return {
                "success": False,
                "status": "REFACTOR_PLAN_REJECTED",
                "errors": validation_errors,
                "files": self._plan_files(
                    plan
                ),
                "refactor_plan": self._plan_dict(
                    plan
                ),
            }

        replacements = {
            str(
                (
                    self.project_root
                    / item.relative_path
                ).resolve(
                    strict=False
                )
            ): item.new_content
            for item in plan.files
        }
        request = DeveloperRequest(
            goal=plan.objective,
            target="multi_file_refactor",
            mode="multi_file",
            replacements=replacements,
            metadata={
                "source": (
                    "multi_file_refactor_executor"
                ),
                "operation": "refactor",
                "multi_file": True,
                "allow_create": False,
                "rollback_scope": list(
                    plan.rollback_scope
                ),
                "validation_targets": list(
                    plan.validation_targets
                ),
                "impacted_files": list(
                    plan.impacted_files
                ),
                "risk_score": (
                    plan.estimated_risk
                ),
                "risk_level": plan.risk_level,
                "estimated_roi": (
                    plan.estimated_roi
                ),
            },
        )

        try:
            workflow_result = (
                self.developer_controller.run(
                    request,
                    auto_approve=auto_approve,
                    auto_rollback=auto_rollback,
                )
            )
        except Exception as error:
            return {
                "success": False,
                "status": (
                    "REFACTOR_EXECUTION_EXCEPTION"
                ),
                "errors": [
                    f"{type(error).__name__}: {error}",
                ],
                "files": self._plan_files(
                    plan
                ),
                "refactor_plan": plan.to_dict(),
            }

        workflow = self._workflow_dict(
            workflow_result
        )
        status = self._status(
            workflow.get(
                "status",
                "",
            )
        )
        success = bool(
            workflow.get(
                "success",
                False,
            )
        )

        if status == "PREVIEW_READY":
            success = True

        return {
            "success": success,
            "status": status,
            "files_count": len(
                plan.files
            ),
            "files": self._plan_files(
                plan
            ),
            "impacted_files": list(
                plan.impacted_files
            ),
            "rollback_scope": list(
                plan.rollback_scope
            ),
            "auto_approved": bool(
                auto_approve
            ),
            "auto_rollback": bool(
                auto_rollback
            ),
            "refactor_plan": plan.to_dict(),
            "workflow": workflow,
            "errors": list(
                workflow.get(
                    "errors",
                    [],
                )
                or []
            ),
        }

    def _validate_plan(
        self,
        plan: MultiFileRefactorPlan,
    ) -> list[str]:
        if not isinstance(
            plan,
            MultiFileRefactorPlan,
        ):
            return [
                "Wymagany jest MultiFileRefactorPlan.",
            ]

        errors = list(
            plan.blockers
        )

        if (
            len(plan.files) < 2
            or len(plan.files)
            > self.policy.max_files
        ):
            errors.append(
                "Plan refaktoryzacji musi zawierać od 2 do "
                f"{self.policy.max_files} plików."
            )

        if (
            plan.estimated_risk
            > self.policy.max_risk_score
        ):
            errors.append(
                "Ryzyko refaktoryzacji przekracza "
                f"limit {self.policy.max_risk_score:.1f}."
            )

        expected_scope = {
            item.relative_path
            for item in plan.files
        }

        if set(
            plan.rollback_scope
        ) != expected_scope:
            errors.append(
                "rollback_scope nie odpowiada "
                "wszystkim zmienianym plikom."
            )

        for item in plan.files:
            target = (
                self.project_root
                / item.relative_path
            ).resolve(
                strict=False
            )

            try:
                target.relative_to(
                    self.project_root
                )
            except ValueError:
                errors.append(
                    "Plik znajduje się poza projektem: "
                    f"{item.relative_path}"
                )
                continue

            if (
                not target.is_file()
                or target.is_symlink()
            ):
                errors.append(
                    "Refaktoryzacja wymaga istniejącego "
                    f"zwykłego pliku: {item.relative_path}"
                )

            if not item.new_content.strip():
                errors.append(
                    "Brak nowej zawartości: "
                    f"{item.relative_path}"
                )

        return self._unique(
            errors
        )

    @staticmethod
    def _plan_files(
        plan: Any,
    ) -> list[str]:
        return [
            item.relative_path
            for item in getattr(
                plan,
                "files",
                [],
            )
            if getattr(
                item,
                "relative_path",
                "",
            )
        ]

    @staticmethod
    def _plan_dict(
        plan: Any,
    ) -> dict[str, Any]:
        return (
            plan.to_dict()
            if hasattr(
                plan,
                "to_dict",
            )
            else {}
        )

    @staticmethod
    def _workflow_dict(
        result: Any,
    ) -> dict[str, Any]:
        if hasattr(
            result,
            "as_dict",
        ):
            value = result.as_dict()
            return (
                dict(value)
                if isinstance(
                    value,
                    dict,
                )
                else {}
            )

        if isinstance(
            result,
            dict,
        ):
            return dict(
                result
            )

        return {
            "success": bool(
                getattr(
                    result,
                    "success",
                    False,
                )
            ),
            "status": str(
                getattr(
                    result,
                    "status",
                    "",
                )
            ),
            "errors": list(
                getattr(
                    result,
                    "errors",
                    [],
                )
                or []
            ),
        }

    @staticmethod
    def _status(
        workflow_status: Any,
    ) -> str:
        normalized = str(
            workflow_status
        ).strip().casefold()
        mapping = {
            "waiting_for_approval": (
                "PREVIEW_READY"
            ),
            "approved": "APPROVED",
            "completed": "COMPLETED",
            "failed_and_rolled_back": (
                "FAILED_AND_ROLLED_BACK"
            ),
            "validation_failed": (
                "VALIDATION_FAILED"
            ),
            "execution_failed": (
                "EXECUTION_FAILED"
            ),
            "automatic_approval_blocked": (
                "APPROVAL_BLOCKED"
            ),
            "approval_blocked": (
                "APPROVAL_BLOCKED"
            ),
        }

        return mapping.get(
            normalized,
            normalized.upper()
            or "UNKNOWN",
        )

    @staticmethod
    def _unique(
        values: list[str],
    ) -> list[str]:
        result: list[str] = []

        for value in values:
            text = str(
                value
            ).strip()

            if text and text not in result:
                result.append(
                    text
                )

        return result
