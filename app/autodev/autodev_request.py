from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict


@dataclass
class AutoDevRequest:

    command: str

    operation: str = "analyze"

    query: str = ""

    reason: str = ""

    metadata: Dict[str, str] = field(
        default_factory=dict
    )

    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )

    def validate(
        self
    ) -> tuple[bool, list[str]]:

        errors = []

        if not self.command.strip():
            errors.append(
                "Brak polecenia AutoDev."
            )

        allowed_operations = {
            "analyze",
            "search",
            "report",
            "status",
            "preview",
            "approve",
            "reject",
            "execute",
            "approve_and_execute",
            "rollback",
            "reset"
        }

        if self.operation not in allowed_operations:
            errors.append(
                "Nieobsługiwana operacja AutoDev: "
                f"{self.operation}"
            )

        if (
            self.operation in {
                "analyze",
                "search"
            }
            and not self.query.strip()
        ):
            errors.append(
                "Brak treści do analizy."
            )

        return not errors, errors

    def summary(
        self
    ) -> str:

        lines = [
            "AUTODEV REQUEST",
            f"Polecenie: {self.command}",
            f"Operacja: {self.operation}",
            f"Zapytanie: {self.query or 'brak'}",
            f"Powód: {self.reason or 'brak'}",
            f"Utworzono: {self.created_at}"
        ]

        if self.metadata:
            lines.append("")
            lines.append("Metadata:")

            for key, value in self.metadata.items():
                lines.append(
                    f"- {key}: {value}"
                )

        return "\n".join(lines)