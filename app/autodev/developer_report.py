from __future__ import annotations

from datetime import datetime
from typing import Any


class DeveloperReport:

    def build(
        self,
        goal: str,
        target: str,
        impacted_files: list,
        task_summary: str,
        success: bool,
        notes: list | None = None,
        lessons: list | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> str:

        notes = notes or []
        lessons = lessons or []
        metadata = metadata or {}

        lines = [
            "AUTODEV REPORT",
            f"Data: {datetime.now().isoformat()}",
            f"Cel: {goal}",
            f"Target: {target or 'brak'}",
            f"Status: {'SUCCESS' if success else 'FAILED'}",
            f"Pliki zależne: {len(impacted_files)}",
            "",
        ]

        if impacted_files:
            lines.append("Pliki do sprawdzenia:")

            for path in impacted_files[:30]:
                lines.append(f"- {path}")

            lines.append("")

        if notes:
            lines.append("Notatki:")

            for note in notes[-20:]:
                lines.append(f"- {note}")

            lines.append("")

        if lessons:
            lines.append("Wnioski:")

            for lesson in lessons[-10:]:
                lines.append(f"- {lesson}")

            lines.append("")

        if metadata:
            lines.append("Metadane:")

            for key, value in sorted(metadata.items()):
                lines.append(f"- {key}: {value}")

            lines.append("")

        lines.append(task_summary)

        return "\n".join(lines)

    def build_dict(
        self,
        *,
        goal: str,
        target: str,
        impacted_files: list,
        task_summary: str,
        success: bool,
        notes: list | None = None,
        lessons: list | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return {
            "success": success,
            "goal": goal,
            "target": target,
            "impacted_files": list(impacted_files),
            "notes": list(notes or []),
            "lessons": list(lessons or []),
            "metadata": dict(metadata or {}),
            "report": self.build(
                goal=goal,
                target=target,
                impacted_files=impacted_files,
                task_summary=task_summary,
                success=success,
                notes=notes,
                lessons=lessons,
                metadata=metadata,
            ),
        }

    def build_learning_record(
        self,
        *,
        goal: str,
        target: str,
        success: bool,
        status: str,
        errors: list[str] | None = None,
        lessons: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        return {
            "success": bool(success),
            "status": str(status),
            "goal": str(goal),
            "target": str(target),
            "errors": list(errors or []),
            "lessons": list(lessons or []),
            "metadata": dict(metadata or {}),
            "created_at": datetime.now().isoformat(),
        }
