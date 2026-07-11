from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List


@dataclass
class FileChange:
    path: str
    old_content: str
    new_content: str
    status: str = "pending"
    error: str = ""


@dataclass
class ChangeTransaction:
    goal: str
    target: str = ""
    changes: List[FileChange] = field(default_factory=list)
    status: str = "created"
    backup_bundle_path: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )
    metadata: Dict[str, str] = field(default_factory=dict)

    def add_change(
        self,
        path: str,
        old_content: str,
        new_content: str
    ) -> FileChange:
        change = FileChange(
            path=path,
            old_content=old_content,
            new_content=new_content
        )

        self.changes.append(change)
        return change

    def files(self) -> list[str]:
        return [
            change.path
            for change in self.changes
        ]

    def validate(self) -> tuple[bool, list[str]]:
        errors = []

        if not self.goal.strip():
            errors.append("Brak celu transakcji.")

        if not self.changes:
            errors.append("Transakcja nie zawiera zmian.")

        seen_paths = set()

        for change in self.changes:
            file_path = Path(change.path)

            if change.path in seen_paths:
                errors.append(
                    f"Plik występuje kilka razy: {change.path}"
                )

            seen_paths.add(change.path)

            if not file_path.exists():
                errors.append(
                    f"Plik nie istnieje: {change.path}"
                )

            if change.old_content == change.new_content:
                errors.append(
                    f"Brak rzeczywistej zmiany w pliku: {change.path}"
                )

        return not errors, errors

    def mark_backed_up(self, bundle_path: str):
        self.backup_bundle_path = bundle_path
        self.status = "backed_up"

    def mark_applying(self):
        self.status = "applying"

    def mark_applied(self):
        self.status = "applied"

    def mark_validated(self):
        self.status = "validated"

    def mark_failed(self):
        self.status = "failed"

    def mark_rolled_back(self):
        self.status = "rolled_back"

    def summary(self) -> str:
        lines = [
            "CHANGE TRANSACTION",
            f"Cel: {self.goal}",
            f"Target: {self.target or 'brak'}",
            f"Status: {self.status}",
            f"Pliki: {len(self.changes)}",
            f"Backup: {self.backup_bundle_path or 'brak'}",
            f"Utworzono: {self.created_at}"
        ]

        if self.changes:
            lines.append("")
            lines.append("Zmiany:")

            for change in self.changes:
                lines.append(
                    f"- {change.path} | "
                    f"status: {change.status}"
                )

                if change.error:
                    lines.append(
                        f"  błąd: {change.error}"
                    )

        return "\n".join(lines)