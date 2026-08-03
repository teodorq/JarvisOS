from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List

from app.autodev.error_reporting import AutoDevErrorReporter


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
    error_details: List[Dict[str, Any]] = field(
        default_factory=list
    )

    def add_error(
        self,
        error: str,
        *,
        details: Dict[str, Any] | None = None,
    ) -> None:
        text = str(error).strip()

        if text and text not in self.errors:
            self.errors.append(text)

        if (
            details
            and details not in self.error_details
        ):
            self.error_details.append(
                dict(details)
            )

        if text or details:
            self.success = False

    def add_exception(
        self,
        error: BaseException,
        *,
        stage: str | None = None,
        context: Dict[str, Any] | None = None,
        project_root: str | None = None,
    ) -> Dict[str, Any]:
        report = AutoDevErrorReporter.capture(
            error,
            stage=stage or self.step_name,
            context=context,
            project_root=project_root,
        )
        details = report.as_dict()
        self.add_error(
            report.summary(),
            details=details,
        )
        return details

    def as_dict(self) -> dict:
        return {
            "success": self.success,
            "step_name": self.step_name,
            "message": self.message,
            "data": self.data,
            "errors": list(self.errors),
            "created_at": self.created_at,
            "error_details": [
                dict(item)
                for item in self.error_details
            ],
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