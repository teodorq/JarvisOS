from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

from .refactor_models import (
    MultiFileRefactorPlan,
)
from .refactor_source_index import (
    RefactorSourceIndex,
)


class MultiFileRefactorVerifier:
    """Verifies preview, completion and rollback invariants."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        source_index: RefactorSourceIndex | None = None,
    ) -> None:
        self.project_root = Path(
            project_root
        ).expanduser().resolve(
            strict=False
        )
        self.source_index = (
            source_index
            or RefactorSourceIndex(
                self.project_root
            )
        )

    def verify(
        self,
        plan: MultiFileRefactorPlan,
        execution: dict[str, Any],
    ) -> dict[str, Any]:
        if not isinstance(
            plan,
            MultiFileRefactorPlan,
        ):
            return {
                "success": False,
                "status": "INVALID_REFACTOR_PLAN",
                "execution_status": "UNKNOWN",
                "checked_files": [],
                "unexpected_changes": [],
                "errors": [
                    "Wymagany jest MultiFileRefactorPlan.",
                ],
            }

        status = str(
            execution.get(
                "status",
                "UNKNOWN",
            )
        ).strip().upper()
        errors: list[str] = []
        checked_files: list[
            dict[str, Any]
        ] = []
        target_map = plan.file_map()
        expected_files = set(
            target_map
        )
        execution_files = {
            str(value).replace(
                "\\",
                "/",
            )
            for value in execution.get(
                "files",
                [],
            )
            if str(value).strip()
        }

        if (
            execution_files
            and execution_files
            != expected_files
        ):
            errors.append(
                "Lista plików wykonania nie odpowiada "
                "planowi refaktoryzacji."
            )

        rolled_back = (
            "ROLLED_BACK" in status
        )
        preview = (
            status == "PREVIEW_READY"
        )
        completed = (
            status == "COMPLETED"
        )
        expected_hashes = (
            plan.baseline_hashes
            if preview or rolled_back
            else {
                **plan.baseline_hashes,
                **{
                    item.relative_path: (
                        item.new_sha256
                    )
                    for item in plan.files
                },
            }
        )

        for relative in sorted(
            set(
                plan.impacted_files
            )
            | expected_files
        ):
            target = (
                self.project_root
                / relative
            ).resolve(
                strict=False
            )
            expected_hash = (
                expected_hashes.get(
                    relative,
                    "",
                )
            )
            exists = target.is_file()
            current_hash = (
                self.source_index.hash_path(
                    target
                )
                if exists
                else ""
            )
            syntax_valid: bool | None = None
            is_target = relative in target_map

            if not exists:
                errors.append(
                    "Brak pliku podczas weryfikacji: "
                    f"{relative}"
                )
            else:
                if expected_hash and (
                    current_hash
                    != expected_hash
                ):
                    if is_target:
                        errors.append(
                            "Nieoczekiwana zawartość pliku "
                            f"refaktoryzacji: {relative}"
                        )
                    else:
                        errors.append(
                            "Refaktoryzacja zmieniła plik "
                            "spoza transakcji: "
                            f"{relative}"
                        )

                if (
                    is_target
                    and completed
                ):
                    syntax_valid = (
                        self._syntax_error(
                            target
                        )
                        == ""
                    )

                    if not syntax_valid:
                        errors.append(
                            "Błąd składni po refaktoryzacji: "
                            f"{relative}"
                        )

            checked_files.append(
                {
                    "path": relative,
                    "target": is_target,
                    "exists": exists,
                    "expected_sha256": (
                        expected_hash
                    ),
                    "current_sha256": (
                        current_hash
                    ),
                    "syntax_valid": (
                        syntax_valid
                    ),
                }
            )

        unexpected_changes = [
            item["path"]
            for item in checked_files
            if (
                not item["target"]
                and item["expected_sha256"]
                and item["current_sha256"]
                != item["expected_sha256"]
            )
        ]

        if not (
            preview
            or completed
            or rolled_back
        ):
            errors.append(
                "Nieobsługiwany status wykonania "
                f"do weryfikacji: {status}"
            )

        return {
            "success": not errors,
            "status": (
                "VERIFIED"
                if not errors
                else "VERIFICATION_FAILED"
            ),
            "execution_status": status,
            "checked_files": checked_files,
            "unexpected_changes": (
                unexpected_changes
            ),
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
            text = str(
                value
            ).strip()

            if text and text not in result:
                result.append(
                    text
                )

        return result
