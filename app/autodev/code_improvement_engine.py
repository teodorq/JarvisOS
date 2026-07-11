from __future__ import annotations

from pathlib import Path
from typing import Any


class CodeImprovementEngine:

    MODULE_PATHS = {
        "brain": "app/ai/brain.py",
        "autodev": "app/autodev",
        "reasoning": "app/ai/reasoner",
        "memory": "app/memory",
        "vision": "app/vision",
        "planner": "app/ai/planner",
        "ui": "app/gui",
    }

    def __init__(
        self,
        project_root: str = "C:/JarvisAI",
    ) -> None:

        self.project_root = Path(
            project_root
        ).resolve()

        self.last_result: dict[str, Any] | None = None

    def analyze_task(
        self,
        task: dict[str, Any],
    ) -> dict[str, Any]:

        title = str(
            task.get(
                "title",
                "",
            )
        ).strip()

        description = str(
            task.get(
                "description",
                "",
            )
        ).strip()

        combined_text = (
            f"{title} {description}"
        ).casefold()

        module_name = self._detect_module(
            combined_text
        )

        target_path = self._resolve_target(
            module_name
        )

        files = self._collect_python_files(
            target_path
        )

        result = {
            "success": bool(
                files
            ),
            "status": (
                "TARGET_FOUND"
                if files
                else "TARGET_NOT_FOUND"
            ),
            "module": module_name,
            "target_path": str(
                target_path
            ),
            "files_count": len(
                files
            ),
            "files": files,
            "task": dict(
                task
            ),
        }

        self.last_result = dict(
            result
        )

        return result

    def _detect_module(
        self,
        text: str,
    ) -> str:

        for module_name in self.MODULE_PATHS:
            if module_name in text:
                return module_name

        return "autodev"

    def _resolve_target(
        self,
        module_name: str,
    ) -> Path:

        relative_path = self.MODULE_PATHS.get(
            module_name,
            self.MODULE_PATHS["autodev"],
        )

        return (
            self.project_root
            / relative_path
        ).resolve()

    def _collect_python_files(
        self,
        target_path: Path,
    ) -> list[str]:

        if target_path.is_file():

            if target_path.suffix == ".py":
                return [
                    str(
                        target_path
                    )
                ]

            return []

        if not target_path.exists():
            return []

        files = sorted(
            target_path.rglob(
                "*.py"
            )
        )

        return [
            str(
                file_path
            )
            for file_path in files
            if "__pycache__" not in file_path.parts
        ][:100]

    def status(
        self,
    ) -> dict[str, Any]:

        return {
            "project_root": str(
                self.project_root
            ),
            "last_result": self.last_result,
        }