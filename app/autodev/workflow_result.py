from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.autodev.change_transaction import ChangeTransaction
from app.autodev.execution_result import ExecutionResult


@dataclass
class WorkflowResult:

    success: bool
    status: str
    message: str
    preview: str = ""
    transaction: Optional[ChangeTransaction] = None
    execution_result: Optional[ExecutionResult] = None
    errors: List[str] = field(default_factory=list)
    data: Dict[str, Any] = field(default_factory=dict)
    learning_data: Dict[str, Any] = field(
        default_factory=dict
    )
    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )

    def add_error(
        self,
        error: str,
    ) -> None:

        if not error:
            return

        self.errors.append(str(error))
        self.success = False

    def add_lesson(
        self,
        lesson: str,
    ) -> None:

        text = str(lesson).strip()

        if not text:
            return

        lessons = self.learning_data.setdefault(
            "lessons",
            [],
        )

        if text not in lessons:
            lessons.append(text)

    def as_dict(
        self,
    ) -> dict[str, Any]:

        transaction_data = None

        if self.transaction is not None:
            transaction_data = {
                "goal": self.transaction.goal,
                "target": self.transaction.target,
                "status": self.transaction.status,
                "files": self.transaction.files(),
                "backup_bundle_path": (
                    self.transaction.backup_bundle_path
                ),
            }

        execution_data = None

        if self.execution_result is not None:
            execution_data = self.execution_result.as_dict()

        return {
            "success": self.success,
            "status": self.status,
            "message": self.message,
            "preview": self.preview,
            "transaction": transaction_data,
            "execution_result": execution_data,
            "errors": list(self.errors),
            "data": dict(self.data),
            "learning_data": dict(self.learning_data),
            "created_at": self.created_at,
        }

    def summary(
        self,
    ) -> str:

        lines = [
            "AUTODEV WORKFLOW RESULT",
            f"Status: {self.status}",
            (
                "Sukces: TAK"
                if self.success
                else "Sukces: NIE"
            ),
            f"Wiadomość: {self.message}",
            f"Data: {self.created_at}",
        ]

        if self.transaction is not None:
            lines.append("")
            lines.append(self.transaction.summary())

        if self.execution_result is not None:
            lines.append("")
            lines.append(
                self.execution_result.summary()
            )

        if self.errors:
            lines.append("")
            lines.append("Błędy:")

            for error in self.errors:
                lines.append(f"- {error}")

        if self.learning_data:
            lines.append("")
            lines.append("Dane uczenia:")

            for key, value in self.learning_data.items():
                lines.append(f"- {key}: {value}")

        if self.data:
            lines.append("")
            lines.append("Dane workflow:")

            for key, value in self.data.items():
                lines.append(f"- {key}: {value}")

        return "\n".join(lines)
