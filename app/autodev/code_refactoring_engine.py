from __future__ import annotations

import ast
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class RefactoringResult:
    success: bool
    status: str
    path: str = ""
    issue_type: str = ""
    old_content: str = ""
    proposed_content: str = ""
    explanation: str = ""
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class CodeRefactoringEngine:
    """
    Deterministyczny, lokalny generator minimalnych zmian.

    Obsługuje tylko małe, przewidywalne poprawki.
    Dla złożonych refaktoryzacji zwraca NEEDS_LLM.
    """

    def __init__(
        self,
        project_root: str = "C:/JarvisAI",
    ) -> None:

        self.project_root = Path(
            project_root
        ).resolve()

        self.last_result: RefactoringResult | None = None

    def refactor(
        self,
        *,
        path: str,
        issue_type: str,
        line: int = 0,
    ) -> RefactoringResult:

        file_path = self._resolve_path(
            path
        )

        if not file_path.exists():
            return self._finish(
                RefactoringResult(
                    success=False,
                    status="FILE_NOT_FOUND",
                    path=str(file_path),
                    issue_type=issue_type,
                    errors=[
                        "Plik nie istnieje."
                    ],
                )
            )

        try:
            old_content = file_path.read_text(
                encoding="utf-8"
            )
        except Exception as error:
            return self._finish(
                RefactoringResult(
                    success=False,
                    status="READ_FAILED",
                    path=str(file_path),
                    issue_type=issue_type,
                    errors=[
                        (
                            f"{type(error).__name__}: "
                            f"{error}"
                        )
                    ],
                )
            )

        normalized_type = str(
            issue_type
        ).strip().upper()

        if normalized_type == "EMPTY_BLOCK":
            proposed, explanation = self._replace_pass(
                old_content,
                line,
            )

        elif normalized_type == "BROAD_EXCEPTION":
            proposed, explanation = (
                self._annotate_exception(
                    old_content,
                    line,
                )
            )

        elif normalized_type == "TODO":
            proposed, explanation = self._annotate_todo(
                old_content,
                line,
            )

        else:
            return self._finish(
                RefactoringResult(
                    success=False,
                    status="NEEDS_LLM",
                    path=str(file_path),
                    issue_type=normalized_type,
                    old_content=old_content,
                    errors=[
                        (
                            "Ten typ refaktoryzacji wymaga "
                            "zewnętrznego generatora kodu."
                        )
                    ],
                )
            )

        if proposed == old_content:
            return self._finish(
                RefactoringResult(
                    success=False,
                    status="NO_SAFE_CHANGE",
                    path=str(file_path),
                    issue_type=normalized_type,
                    old_content=old_content,
                    proposed_content=proposed,
                    errors=[
                        "Nie znaleziono bezpiecznej zmiany."
                    ],
                )
            )

        syntax_error = self._syntax_error(
            proposed,
            file_path,
        )

        if syntax_error:
            return self._finish(
                RefactoringResult(
                    success=False,
                    status="INVALID_PROPOSAL",
                    path=str(file_path),
                    issue_type=normalized_type,
                    old_content=old_content,
                    proposed_content=proposed,
                    errors=[
                        syntax_error
                    ],
                )
            )

        return self._finish(
            RefactoringResult(
                success=True,
                status="REFACTOR_READY",
                path=str(file_path),
                issue_type=normalized_type,
                old_content=old_content,
                proposed_content=proposed,
                explanation=explanation,
                warnings=[
                    "Zmiana wymaga walidacji i akceptacji."
                ],
            )
        )

    def _replace_pass(
        self,
        content: str,
        line: int,
    ) -> tuple[str, str]:

        lines = content.splitlines(
            keepends=True
        )

        index = line - 1

        if index < 0 or index >= len(lines):
            return content, ""

        raw = lines[index]

        if raw.strip() != "pass":
            return content, ""

        indent = raw[
            :len(raw) - len(raw.lstrip())
        ]

        newline = (
            "\r\n"
            if raw.endswith("\r\n")
            else "\n"
        )

        lines[index] = (
            f"{indent}raise NotImplementedError("
            "\"AutoDev: implementacja wymagana.\""
            f"){newline}"
        )

        return (
            "".join(lines),
            (
                "Pusty blok zastąpiono jawnym "
                "NotImplementedError."
            ),
        )

    def _annotate_exception(
        self,
        content: str,
        line: int,
    ) -> tuple[str, str]:

        lines = content.splitlines(
            keepends=True
        )

        index = line - 1

        if index < 0 or index >= len(lines):
            return content, ""

        raw = lines[index]
        stripped = raw.strip()

        if not (
            stripped.startswith(
                "except Exception"
            )
            and stripped.endswith(
                ":"
            )
        ):
            return content, ""

        indent = raw[
            :len(raw) - len(raw.lstrip())
        ]

        newline = (
            "\r\n"
            if raw.endswith("\r\n")
            else "\n"
        )

        marker = (
            f"{indent}# AUTODEV_REVIEW_EXCEPTION"
            f"{newline}"
        )

        if (
            index > 0
            and "AUTODEV_REVIEW_EXCEPTION"
            in lines[index - 1]
        ):
            return content, ""

        lines.insert(
            index,
            marker,
        )

        return (
            "".join(lines),
            (
                "Dodano znacznik do dalszego "
                "zawężenia wyjątku."
            ),
        )

    def _annotate_todo(
        self,
        content: str,
        line: int,
    ) -> tuple[str, str]:

        lines = content.splitlines(
            keepends=True
        )

        index = line - 1

        if index < 0 or index >= len(lines):
            return content, ""

        raw = lines[index]

        if "todo" not in raw.casefold():
            return content, ""

        if "AUTODEV_REVIEWED" in raw:
            return content, ""

        newline = (
            "\r\n"
            if raw.endswith("\r\n")
            else "\n"
        )

        lines[index] = (
            raw.rstrip("\r\n")
            + "  # AUTODEV_REVIEWED"
            + newline
        )

        return (
            "".join(lines),
            "Oznaczono TODO do dalszej implementacji.",
        )

    def _resolve_path(
        self,
        path: str,
    ) -> Path:

        candidate = Path(
            path
        )

        if not candidate.is_absolute():
            candidate = (
                self.project_root
                / candidate
            )

        resolved = candidate.resolve()

        try:
            resolved.relative_to(
                self.project_root
            )
        except ValueError as error:
            raise ValueError(
                "Ścieżka poza projektem."
            ) from error

        return resolved

    def _syntax_error(
        self,
        content: str,
        path: Path,
    ) -> str | None:

        try:
            ast.parse(
                content,
                filename=str(path),
            )
            return None

        except SyntaxError as error:
            return (
                f"Błąd składni w linii "
                f"{error.lineno or 0}: "
                f"{error.msg}"
            )

    def _finish(
        self,
        result: RefactoringResult,
    ) -> RefactoringResult:

        self.last_result = result
        return result

    def status(
        self,
    ) -> dict[str, Any]:

        return {
            "project_root": str(
                self.project_root
            ),
            "last_result": (
                self.last_result.to_dict()
                if self.last_result is not None
                else None
            ),
        }
