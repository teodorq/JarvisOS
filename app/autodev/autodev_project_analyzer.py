from __future__ import annotations

from pathlib import Path
from typing import Any

from app.autodev.autodev_project_snapshot import (
    AutoDevProjectSnapshot,
)


class AutoDevProjectAnalyzer:
    """
    Lekka analiza projektu bez wykonywania kodu.
    """

    def __init__(
        self,
        project_root: str = "C:/JarvisAI",
    ) -> None:
        self.project_root = Path(project_root).resolve()
        self.last_result: dict[str, Any] | None = None

    def analyze(self) -> dict[str, Any]:
        files_count = 0
        python_files_count = 0
        total_lines = 0
        errors: list[str] = []

        if not self.project_root.exists():
            result = {
                "success": False,
                "status": "PROJECT_NOT_FOUND",
                "project_root": str(self.project_root),
                "snapshot": AutoDevProjectSnapshot.create(
                    files_count=0,
                    python_files_count=0,
                    total_lines=0,
                    errors=["Nie znaleziono katalogu projektu."],
                ).to_dict(),
                "writes_code": False,
            }
            self.last_result = dict(result)
            return result

        for path in self.project_root.rglob("*"):
            if not path.is_file():
                continue

            files_count += 1

            if path.suffix.lower() != ".py":
                continue

            python_files_count += 1

            try:
                content = path.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
                total_lines += len(content.splitlines())
            except OSError as error:
                errors.append(
                    f"{path}: {type(error).__name__}: {error}"
                )

        snapshot = AutoDevProjectSnapshot.create(
            files_count=files_count,
            python_files_count=python_files_count,
            total_lines=total_lines,
            errors=errors,
            metadata={
                "project_root": str(self.project_root),
            },
        )

        result = {
            "success": True,
            "status": "PROJECT_ANALYZED",
            "project_root": str(self.project_root),
            "snapshot": snapshot.to_dict(),
            "writes_code": False,
        }

        self.last_result = dict(result)
        return result

    def status(self) -> dict[str, Any]:
        return {
            "project_root": str(self.project_root),
            "last_result": self.last_result,
        }
