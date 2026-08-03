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
from app.autodev.execution_policy import (
    ExecutionPolicy,
    ProjectBoundaryPolicy,
)

from .feature_code_generator import (
    FeatureCodeGenerator,
)
from .feature_models import FeatureBlueprint


@dataclass(frozen=True, slots=True)
class MultiFileExecutionPolicy:
    max_files: int = 12
    allow_existing: bool = False

    def __post_init__(self) -> None:
        if self.max_files < 2:
            raise ValueError(
                "max_files musi wynosić co najmniej 2."
            )


class MultiFileFeatureExecutor:
    """Executes an entire feature blueprint as one transaction."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        developer_controller: DeveloperController | None = None,
        code_generator: FeatureCodeGenerator | None = None,
        policy: MultiFileExecutionPolicy | None = None,
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
        self.code_generator = (
            code_generator
            or FeatureCodeGenerator()
        )
        self.policy = (
            policy
            or MultiFileExecutionPolicy()
        )
        self.boundary = ProjectBoundaryPolicy(
            ExecutionPolicy(
                project_root=self.project_root,
                allowed_extensions=(
                    ".py",
                ),
            )
        )

    def execute(
        self,
        blueprint: FeatureBlueprint,
        *,
        auto_approve: bool = False,
        auto_rollback: bool = True,
        replacements: dict[str, str] | None = None,
        allow_existing: bool | None = None,
    ) -> dict[str, Any]:
        validation = self._validate_blueprint(
            blueprint,
            allow_existing=(
                self.policy.allow_existing
                if allow_existing is None
                else bool(
                    allow_existing
                )
            ),
        )

        if validation["errors"]:
            return {
                "success": False,
                "status": "FEATURE_VALIDATION_FAILED",
                "errors": validation["errors"],
                "feature_blueprint": (
                    blueprint.to_dict()
                    if isinstance(
                        blueprint,
                        FeatureBlueprint,
                    )
                    else {}
                ),
                "files": validation["files"],
            }

        try:
            generated = self.code_generator.generate(
                blueprint,
                overrides=replacements,
            )
        except Exception as error:
            return {
                "success": False,
                "status": "FEATURE_GENERATION_FAILED",
                "errors": [
                    f"{type(error).__name__}: {error}",
                ],
                "feature_blueprint": blueprint.to_dict(),
                "files": validation["files"],
            }

        absolute_replacements = {
            str(
                self._resolve_target(
                    path
                )
            ): content
            for path, content in generated.items()
        }
        risk_level = (
            "MEDIUM"
            if blueprint.estimated_risk
            > 0.45
            else "LOW"
        )
        request = DeveloperRequest(
            goal=blueprint.objective,
            target=blueprint.package_path,
            mode="multi_file",
            replacements=absolute_replacements,
            metadata={
                "source": "multi_file_feature_executor",
                "multi_file": True,
                "allow_create": True,
                "feature_name": blueprint.feature_name,
                "feature_slug": blueprint.feature_slug,
                "package_path": blueprint.package_path,
                "creation_order": list(
                    blueprint.creation_order
                ),
                "rollback_scope": list(
                    blueprint.rollback_scope
                ),
                "validation_targets": list(
                    blueprint.validation_targets
                ),
                "risk_score": blueprint.estimated_risk,
                "risk_level": risk_level,
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
                "status": "FEATURE_EXECUTION_EXCEPTION",
                "errors": [
                    f"{type(error).__name__}: {error}",
                ],
                "feature_blueprint": blueprint.to_dict(),
                "files": validation["files"],
            }

        workflow = self._workflow_dict(
            workflow_result
        )
        status = self._status(
            str(
                workflow.get(
                    "status",
                    "",
                )
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
            "feature_name": blueprint.feature_name,
            "package_path": blueprint.package_path,
            "files_count": len(
                generated
            ),
            "files": list(
                generated
            ),
            "creation_order": list(
                blueprint.creation_order
            ),
            "validation_targets": list(
                blueprint.validation_targets
            ),
            "rollback_scope": list(
                blueprint.rollback_scope
            ),
            "auto_approved": bool(
                auto_approve
            ),
            "auto_rollback": bool(
                auto_rollback
            ),
            "feature_blueprint": blueprint.to_dict(),
            "workflow": workflow,
            "errors": list(
                workflow.get(
                    "errors",
                    [],
                )
                or []
            ),
        }

    def _validate_blueprint(
        self,
        blueprint: FeatureBlueprint,
        *,
        allow_existing: bool,
    ) -> dict[str, Any]:
        errors: list[str] = []
        files: list[str] = []

        if not isinstance(
            blueprint,
            FeatureBlueprint,
        ):
            return {
                "errors": [
                    "Wymagany jest obiekt FeatureBlueprint.",
                ],
                "files": [],
            }

        if (
            len(blueprint.files) < 2
            or len(blueprint.files)
            > self.policy.max_files
        ):
            errors.append(
                "Blueprint musi zawierać od 2 do "
                f"{self.policy.max_files} plików."
            )

        blueprint_paths = {
            item.relative_path.replace(
                "\\",
                "/",
            )
            for item in blueprint.files
        }

        if set(
            blueprint.rollback_scope
        ) != {
            item.relative_path
            for item in blueprint.files
            if item.required
        }:
            errors.append(
                "rollback_scope nie odpowiada "
                "wymaganym plikom blueprintu."
            )

        for item in blueprint.files:
            try:
                target = self._resolve_target(
                    item.relative_path
                )
                files.append(
                    str(target)
                )

                if (
                    target.exists()
                    and not allow_existing
                ):
                    errors.append(
                        "Target już istnieje: "
                        f"{item.relative_path}"
                    )

            except Exception as error:
                errors.append(
                    f"{item.relative_path}: {error}"
                )

        if set(
            blueprint.creation_order
        ) != {
            item.file_id
            for item in blueprint.files
        }:
            errors.append(
                "creation_order nie obejmuje "
                "dokładnie wszystkich plików."
            )

        if len(blueprint_paths) != len(
            blueprint.files
        ):
            errors.append(
                "Blueprint zawiera duplikaty ścieżek."
            )

        return {
            "errors": self._unique(
                errors
            ),
            "files": files,
        }

    def _resolve_target(
        self,
        relative_path: str,
    ) -> Path:
        return self.boundary.resolve_target(
            relative_path,
            require_file=False,
            allow_missing=True,
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
        workflow_status: str,
    ) -> str:
        normalized = (
            str(
                workflow_status
            )
            .strip()
            .casefold()
        )
        mapping = {
            "waiting_for_approval": "PREVIEW_READY",
            "approved": "APPROVED",
            "completed": "COMPLETED",
            "failed_and_rolled_back": (
                "FAILED_AND_ROLLED_BACK"
            ),
            "validation_failed": "VALIDATION_FAILED",
            "execution_failed": "EXECUTION_FAILED",
            "automatic_approval_blocked": (
                "APPROVAL_BLOCKED"
            ),
            "approval_blocked": "APPROVAL_BLOCKED",
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
            if value not in result:
                result.append(
                    value
                )

        return result
