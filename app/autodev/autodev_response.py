from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List


@dataclass
class AutoDevResponse:

    success: bool

    operation: str

    message: str

    report: str = ""

    data: Dict[str, Any] = field(
        default_factory=dict
    )

    errors: List[str] = field(
        default_factory=list
    )

    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )

    def add_error(
        self,
        error: str
    ):

        if not error:
            return

        self.errors.append(
            str(error)
        )

        self.success = False

    def as_dict(
        self
    ) -> dict:

        return {
            "success": self.success,
            "operation": self.operation,
            "message": self.message,
            "report": self.report,
            "data": self.data,
            "errors": self.errors,
            "created_at": self.created_at
        }

    def summary(
        self
    ) -> str:

        lines = [
            "AUTODEV RESPONSE",
            (
                "Status: SUCCESS"
                if self.success
                else "Status: FAILED"
            ),
            f"Operacja: {self.operation}",
            f"Wiadomość: {self.message}",
            f"Data: {self.created_at}"
        ]

        if self.report:
            lines.append("")
            lines.append(self.report)

        if self.data:
            lines.append("")
            lines.append("Dane:")

            for key, value in self.data.items():
                lines.append(
                    f"- {key}: {value}"
                )

        if self.errors:
            lines.append("")
            lines.append("Błędy:")

            for error in self.errors:
                lines.append(
                    f"- {error}"
                )

        return "\n".join(lines)