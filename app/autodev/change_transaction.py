from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
import os
from pathlib import Path
from typing import Any


@dataclass
class FileChange:
    path: str
    old_content: str
    new_content: str
    status: str = "pending"
    error: str = ""
    operation: str = "update"

    @property
    def creates_file(self) -> bool:
        return (
            str(self.operation)
            .strip()
            .casefold()
            == "create"
        )


@dataclass
class ChangeTransaction:
    goal: str
    target: str = ""
    changes: list[FileChange] = field(
        default_factory=list
    )
    status: str = "created"
    backup_bundle_path: str = ""
    created_at: str = field(
        default_factory=lambda: (
            datetime.now().isoformat()
        )
    )
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def add_change(
        self,
        path: str,
        old_content: str,
        new_content: str,
        *,
        operation: str = "update",
    ) -> FileChange:
        normalized_operation = (
            str(operation)
            .strip()
            .casefold()
            or "update"
        )

        change = FileChange(
            path=path,
            old_content=old_content,
            new_content=new_content,
            operation=normalized_operation,
        )
        self.changes.append(
            change
        )
        return change

    def files(self) -> list[str]:
        return [
            change.path
            for change in self.changes
        ]

    def created_files(self) -> list[str]:
        return [
            change.path
            for change in self.changes
            if change.creates_file
        ]

    def existing_files(self) -> list[str]:
        return [
            change.path
            for change in self.changes
            if not change.creates_file
        ]

    def validate(
        self,
    ) -> tuple[bool, list[str]]:
        errors: list[str] = []

        if not self.goal.strip():
            errors.append(
                "Brak celu transakcji."
            )

        if not self.changes:
            errors.append(
                "Transakcja nie zawiera zmian."
            )

        seen_paths: set[str] = set()

        for change in self.changes:
            raw_path = str(
                change.path
            ).strip()
            file_path = Path(
                raw_path
            )
            operation = (
                str(
                    change.operation
                )
                .strip()
                .casefold()
            )

            if not raw_path:
                errors.append(
                    "Zmiana zawiera pustą ścieżkę pliku."
                )
                continue

            normalized_path = os.path.normcase(
                str(
                    file_path.expanduser()
                )
            )

            if normalized_path in seen_paths:
                errors.append(
                    "Plik występuje kilka razy: "
                    f"{change.path}"
                )

            seen_paths.add(
                normalized_path
            )

            if operation not in {
                "update",
                "create",
            }:
                errors.append(
                    "Nieobsługiwana operacja pliku "
                    f"{operation!r}: {change.path}"
                )
                continue

            change.operation = operation

            if operation == "create":
                if file_path.exists():
                    errors.append(
                        "Plik przeznaczony do utworzenia "
                        f"już istnieje: {change.path}"
                    )

                if change.old_content:
                    errors.append(
                        "Nowy plik nie może mieć "
                        f"starej zawartości: {change.path}"
                    )
            else:
                if not file_path.exists():
                    errors.append(
                        f"Plik nie istnieje: {change.path}"
                    )
                elif not file_path.is_file():
                    errors.append(
                        f"Ścieżka nie jest plikiem: {change.path}"
                    )

            if (
                operation == "update"
                and change.old_content
                == change.new_content
            ):
                errors.append(
                    "Brak rzeczywistej zmiany w pliku: "
                    f"{change.path}"
                )

            if (
                operation == "create"
                and not change.new_content
            ):
                errors.append(
                    "Brak zawartości nowego pliku: "
                    f"{change.path}"
                )

        return not errors, errors

    def mark_backed_up(
        self,
        bundle_path: str,
    ) -> None:
        self.backup_bundle_path = bundle_path
        self.status = "backed_up"

    def mark_applying(self) -> None:
        self.status = "applying"

    def mark_applied(self) -> None:
        self.status = "applied"

    def mark_validated(self) -> None:
        self.status = "validated"

    def mark_failed(self) -> None:
        self.status = "failed"

    def mark_rolled_back(self) -> None:
        self.status = "rolled_back"

    def summary(self) -> str:
        lines = [
            "CHANGE TRANSACTION",
            f"Cel: {self.goal}",
            f"Target: {self.target or 'brak'}",
            f"Status: {self.status}",
            f"Pliki: {len(self.changes)}",
            (
                "Nowe pliki: "
                f"{len(self.created_files())}"
            ),
            (
                "Aktualizowane pliki: "
                f"{len(self.existing_files())}"
            ),
            (
                "Backup: "
                f"{self.backup_bundle_path or 'brak'}"
            ),
            f"Utworzono: {self.created_at}",
        ]

        if self.changes:
            lines.append("")
            lines.append("Zmiany:")

            for change in self.changes:
                lines.append(
                    f"- {change.path} | "
                    f"operacja: {change.operation} | "
                    f"status: {change.status}"
                )

                if change.error:
                    lines.append(
                        f"  błąd: {change.error}"
                    )

        return "\n".join(
            lines
        )
