from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List


@dataclass
class ExecutionResult:
    success: bool
    step_name: str
    message: str
    data: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )

    def add_error(self, error: str):
        if error:
            self.errors.append(str(error))
            self.success = False

    def as_dict(self) -> dict:
        return {
            "success": self.success,
            "step_name": self.step_name,
            "message": self.message,
            "data": self.data,
            "errors": self.errors,
            "created_at": self.created_at
        }

    def summary(self) -> str:
        lines = [
            "EXECUTION RESULT",
            f"Krok: {self.step_name}",
            f"Status: {'SUCCESS' if self.success else 'FAILED'}",
            f"Wiadomość: {self.message}",
            f"Data: {self.created_at}"
        ]

        if self.data:
            lines.append("")
            lines.append("Dane:")

            for key, value in self.data.items():
                lines.append(f"- {key}: {value}")

        if self.errors:
            lines.append("")
            lines.append("Błędy:")

            for error in self.errors:
                lines.append(f"- {error}")

        return "\n".join(lines)