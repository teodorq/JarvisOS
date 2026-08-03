from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from app.autodev.execution_policy import (
    ExecutionPolicy,
    ProjectBoundaryPolicy,
)

from .feature_models import FeatureBlueprint


class MultiFileFeatureVerifier:
    """Verifies preview, completion and rollback invariants."""

    def __init__(
        self,
        project_root: str | Path,
    ) -> None:
        self.project_root = Path(
            project_root
        ).expanduser().resolve(
            strict=False
        )
        self.boundary = ProjectBoundaryPolicy(
            ExecutionPolicy(
                project_root=self.project_root,
                allowed_extensions=(
                    ".py",
                ),
            )
        )

    def verify(
        self,
        blueprint: FeatureBlueprint,
        execution: dict[str, Any],
        *,
        allow_existing: bool = False,
    ) -> dict[str, Any]:
        status = str(
            execution.get(
                "status",
                "UNKNOWN",
            )
        ).strip().upper()
        errors: list[str] = []
        checked_files: list[dict[str, Any]] = []

        if not isinstance(
            blueprint,
            FeatureBlueprint,
        ):
            return {
                "success": False,
                "status": "INVALID_BLUEPRINT",
                "checked_files": [],
                "errors": [
                    "Wymagany jest FeatureBlueprint.",
                ],
            }

        expected_paths = {
            item.relative_path.replace(
                "\\",
                "/",
            )
            for item in blueprint.files
        }
        execution_paths = {
            str(path).replace(
                "\\",
                "/",
            )
            for path in execution.get(
                "files",
                [],
            )
            if str(path).strip()
        }

        if execution_paths and execution_paths != expected_paths:
            errors.append(
                "Lista plików wykonania nie odpowiada blueprintowi."
            )

        for item in blueprint.files:
            try:
                target = self.boundary.resolve_target(
                    item.relative_path,
                    require_file=False,
                    allow_missing=True,
                )
            except Exception as error:
                errors.append(
                    f"{item.relative_path}: {error}"
                )
                continue

            exists = target.is_file()
            file_result: dict[str, Any] = {
                "path": item.relative_path,
                "exists": exists,
                "syntax_valid": None,
                "category": item.category,
            }

            if status == "PREVIEW_READY":
                if exists and not allow_existing:
                    errors.append(
                        "Podgląd utworzył plik przed akceptacją: "
                        f"{item.relative_path}"
                    )

            elif status == "COMPLETED":
                if not exists:
                    errors.append(
                        "Brak pliku po zakończeniu: "
                        f"{item.relative_path}"
                    )
                else:
                    syntax_error = self._syntax_error(
                        target
                    )
                    file_result["syntax_valid"] = (
                        not syntax_error
                    )

                    if syntax_error:
                        errors.append(
                            f"{item.relative_path}: {syntax_error}"
                        )

            elif "ROLLED_BACK" in status:
                if exists and not allow_existing:
                    errors.append(
                        "Rollback pozostawił nowy plik: "
                        f"{item.relative_path}"
                    )

            checked_files.append(
                file_result
            )

        if status == "COMPLETED":
            for target in blueprint.validation_targets:
                path = self.boundary.resolve_target(
                    target,
                    require_file=False,
                    allow_missing=True,
                )

                if not path.is_file():
                    errors.append(
                        "Brak celu walidacji: "
                        f"{target}"
                    )

        return {
            "success": not errors,
            "status": (
                "VERIFIED"
                if not errors
                else "VERIFICATION_FAILED"
            ),
            "execution_status": status,
            "expected_files": len(
                blueprint.files
            ),
            "checked_files": checked_files,
            "errors": self._unique(
                errors
            ),
        }

    @staticmethod
    def _syntax_error(
        path: Path,
    ) -> str:
        try:
            source = path.read_text(
                encoding="utf-8"
            )
            ast.parse(
                source,
                filename=str(path),
            )
            return ""
        except Exception as error:
            return (
                f"{type(error).__name__}: {error}"
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
