from __future__ import annotations

import ast
import hashlib
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class CodeGenerationPolicy:
    project_root: str = "C:/JarvisAI"
    max_file_size_bytes: int = 500_000
    max_changed_lines: int = 200
    require_python_file: bool = True
    require_existing_file: bool = True
    allow_empty_block_repair: bool = True
    allow_todo_annotation: bool = True
    allow_broad_exception_annotation: bool = True
    dry_run: bool = True

    def validate(self) -> None:
        if not str(self.project_root).strip():
            raise ValueError("project_root nie może być pusty.")
        if self.max_file_size_bytes < 1:
            raise ValueError("max_file_size_bytes musi być większe od 0.")
        if self.max_changed_lines < 1:
            raise ValueError("max_changed_lines musi być większe od 0.")


@dataclass(slots=True)
class CodePatchCandidate:
    success: bool
    status: str
    path: str = ""
    issue_type: str = ""
    goal: str = ""
    old_content: str = ""
    proposed_content: str = ""
    changed_lines: int = 0
    original_hash: str = ""
    proposed_hash: str = ""
    requires_approval: bool = True
    safe_execution: bool = True
    auto_rollback: bool = True
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def has_change(self) -> bool:
        return self.success and self.old_content != self.proposed_content


class CodeGenerationEngine:
    """Bezpieczny generator kandydatów zmian.

    Moduł nie zapisuje plików i nie wykonuje patcha. Tworzy tylko
    propozycję do późniejszej walidacji, podglądu i akceptacji.
    """

    SUPPORTED_ISSUES = {
        "EMPTY_BLOCK",
        "TODO",
        "BROAD_EXCEPTION",
    }

    def __init__(
        self,
        policy: CodeGenerationPolicy | None = None,
    ) -> None:
        self.policy = policy or CodeGenerationPolicy()
        self.policy.validate()
        self.project_root = Path(self.policy.project_root).resolve()
        self.last_candidate: CodePatchCandidate | None = None
        self.generation_count = 0

    def generate(self, plan: dict[str, Any]) -> CodePatchCandidate:
        self.generation_count += 1

        if not isinstance(plan, dict):
            return self._finish(
                CodePatchCandidate(
                    success=False,
                    status="INVALID_PLAN",
                    errors=["Plan musi być typu dict."],
                )
            )

        issue = plan.get("issue", {})
        if not isinstance(issue, dict):
            issue = {}

        path_value = str(plan.get("path", "")).strip()
        issue_type = str(
            plan.get("issue_type", issue.get("type", ""))
        ).strip().upper()
        goal = str(plan.get("goal", "")).strip()
        line_number = self._safe_int(
            plan.get("line", issue.get("line", 0))
        )

        if not path_value:
            return self._finish(
                CodePatchCandidate(
                    success=False,
                    status="MISSING_PATH",
                    issue_type=issue_type,
                    goal=goal,
                    errors=["Brak ścieżki pliku w planie."],
                )
            )

        file_path = self._resolve_path(path_value)
        path_error = self._validate_path(file_path)
        if path_error:
            return self._finish(
                CodePatchCandidate(
                    success=False,
                    status="UNSAFE_PATH",
                    path=str(file_path),
                    issue_type=issue_type,
                    goal=goal,
                    errors=[path_error],
                )
            )

        file_error = self._validate_file(file_path)
        if file_error:
            return self._finish(
                CodePatchCandidate(
                    success=False,
                    status="FILE_REJECTED",
                    path=str(file_path),
                    issue_type=issue_type,
                    goal=goal,
                    errors=[file_error],
                )
            )

        try:
            old_content = file_path.read_text(encoding="utf-8")
        except Exception as error:
            return self._finish(
                CodePatchCandidate(
                    success=False,
                    status="READ_FAILED",
                    path=str(file_path),
                    issue_type=issue_type,
                    goal=goal,
                    errors=[f"{type(error).__name__}: {error}"],
                )
            )

        original_hash = self._hash(old_content)
        syntax_error = self._syntax_error(old_content, file_path)
        if syntax_error:
            return self._finish(
                CodePatchCandidate(
                    success=False,
                    status="SOURCE_SYNTAX_INVALID",
                    path=str(file_path),
                    issue_type=issue_type,
                    goal=goal,
                    old_content=old_content,
                    original_hash=original_hash,
                    errors=[syntax_error],
                )
            )

        if issue_type not in self.SUPPORTED_ISSUES:
            return self._finish(
                CodePatchCandidate(
                    success=False,
                    status="UNSUPPORTED_ISSUE",
                    path=str(file_path),
                    issue_type=issue_type,
                    goal=goal,
                    old_content=old_content,
                    original_hash=original_hash,
                    warnings=[
                        "Generator nie wykonuje automatycznej refaktoryzacji tego typu."
                    ],
                    errors=[
                        f"Nieobsługiwany typ problemu: {issue_type or 'UNKNOWN'}"
                    ],
                )
            )

        proposed_content, warnings = self._build_proposal(
            content=old_content,
            issue_type=issue_type,
            line_number=line_number,
            issue=issue,
        )

        if proposed_content == old_content:
            return self._finish(
                CodePatchCandidate(
                    success=False,
                    status="NO_SAFE_CHANGE",
                    path=str(file_path),
                    issue_type=issue_type,
                    goal=goal,
                    old_content=old_content,
                    proposed_content=proposed_content,
                    original_hash=original_hash,
                    proposed_hash=self._hash(proposed_content),
                    warnings=warnings,
                    errors=["Nie udało się przygotować bezpiecznej zmiany."],
                )
            )

        changed_lines = self._count_changed_lines(
            old_content,
            proposed_content,
        )

        if changed_lines > self.policy.max_changed_lines:
            return self._finish(
                CodePatchCandidate(
                    success=False,
                    status="CHANGE_TOO_LARGE",
                    path=str(file_path),
                    issue_type=issue_type,
                    goal=goal,
                    old_content=old_content,
                    proposed_content=proposed_content,
                    changed_lines=changed_lines,
                    original_hash=original_hash,
                    proposed_hash=self._hash(proposed_content),
                    warnings=warnings,
                    errors=[
                        "Zmiana przekracza limit "
                        f"{self.policy.max_changed_lines} linii."
                    ],
                )
            )

        proposed_syntax_error = self._syntax_error(
            proposed_content,
            file_path,
        )
        if proposed_syntax_error:
            return self._finish(
                CodePatchCandidate(
                    success=False,
                    status="PROPOSAL_SYNTAX_INVALID",
                    path=str(file_path),
                    issue_type=issue_type,
                    goal=goal,
                    old_content=old_content,
                    proposed_content=proposed_content,
                    changed_lines=changed_lines,
                    original_hash=original_hash,
                    proposed_hash=self._hash(proposed_content),
                    warnings=warnings,
                    errors=[proposed_syntax_error],
                )
            )

        return self._finish(
            CodePatchCandidate(
                success=True,
                status="CANDIDATE_READY",
                path=str(file_path),
                issue_type=issue_type,
                goal=goal,
                old_content=old_content,
                proposed_content=proposed_content,
                changed_lines=changed_lines,
                original_hash=original_hash,
                proposed_hash=self._hash(proposed_content),
                warnings=warnings,
                metadata={
                    "generator": "CodeGenerationEngine",
                    "generated_at": datetime.now().isoformat(),
                    "dry_run": self.policy.dry_run,
                    "line": line_number,
                },
            )
        )

    def _build_proposal(
        self,
        *,
        content: str,
        issue_type: str,
        line_number: int,
        issue: dict[str, Any],
    ) -> tuple[str, list[str]]:
        if issue_type == "EMPTY_BLOCK":
            return self._repair_empty_block(content, line_number)
        if issue_type == "TODO":
            return self._annotate_todo(content, line_number, issue)
        if issue_type == "BROAD_EXCEPTION":
            return self._annotate_broad_exception(content, line_number)
        return content, ["Brak generatora dla wybranego problemu."]

    def _repair_empty_block(
        self,
        content: str,
        line_number: int,
    ) -> tuple[str, list[str]]:
        if not self.policy.allow_empty_block_repair:
            return content, ["Naprawa EMPTY_BLOCK jest wyłączona."]

        lines = content.splitlines(keepends=True)
        index = line_number - 1
        if index < 0 or index >= len(lines):
            return content, ["Podana linia EMPTY_BLOCK nie istnieje."]

        raw_line = lines[index]
        if raw_line.strip() != "pass":
            return content, ["Wskazana linia nie zawiera samego pass."]

        indentation = raw_line[: len(raw_line) - len(raw_line.lstrip())]
        newline = "\r\n" if raw_line.endswith("\r\n") else "\n"
        lines[index] = (
            f'{indentation}raise NotImplementedError('
            '"AutoDev: brak bezpiecznej implementacji.")'
            f"{newline}"
        )

        return "".join(lines), [
            "Pusty blok zastąpiono jawnym NotImplementedError."
        ]

    def _annotate_todo(
        self,
        content: str,
        line_number: int,
        issue: dict[str, Any],
    ) -> tuple[str, list[str]]:
        if not self.policy.allow_todo_annotation:
            return content, ["Obsługa TODO jest wyłączona."]

        lines = content.splitlines(keepends=True)
        index = line_number - 1
        if index < 0 or index >= len(lines):
            return content, ["Podana linia TODO nie istnieje."]

        raw_line = lines[index]
        if "todo" not in raw_line.casefold():
            return content, ["Wskazana linia nie zawiera TODO."]

        marker = "AUTODEV_REVIEWED"
        if marker.casefold() in raw_line.casefold():
            return content, ["TODO zostało już oznaczone przez AutoDev."]

        newline = "\r\n" if raw_line.endswith("\r\n") else "\n"
        line_without_newline = raw_line.rstrip("\r\n")
        message = str(issue.get("message", "")).strip()
        suffix = (
            f"  # {marker}"
            if not message
            else f"  # {marker}: {message[:120]}"
        )
        lines[index] = line_without_newline + suffix + newline

        return "".join(lines), [
            "TODO oznaczono do dalszej implementacji; logika nie została zmieniona."
        ]

    def _annotate_broad_exception(
        self,
        content: str,
        line_number: int,
    ) -> tuple[str, list[str]]:
        if not self.policy.allow_broad_exception_annotation:
            return content, ["Obsługa BROAD_EXCEPTION jest wyłączona."]

        lines = content.splitlines(keepends=True)
        index = line_number - 1
        if index < 0 or index >= len(lines):
            return content, ["Podana linia wyjątku nie istnieje."]

        raw_line = lines[index]
        normalized = raw_line.strip()
        if not (
            normalized.startswith("except Exception")
            and normalized.endswith(":")
        ):
            return content, [
                "Wskazana linia nie jest blokiem except Exception."
            ]

        marker = "AUTODEV_REVIEW_EXCEPTION"
        previous_line = lines[index - 1] if index > 0 else ""
        if marker in previous_line:
            return content, ["Blok wyjątku został już oznaczony."]

        indentation = raw_line[: len(raw_line) - len(raw_line.lstrip())]
        newline = "\r\n" if raw_line.endswith("\r\n") else "\n"
        annotation = (
            f"{indentation}# {marker}: rozważ bardziej precyzyjny wyjątek"
            f"{newline}"
        )
        lines.insert(index, annotation)

        return "".join(lines), [
            "Dodano komentarz bezpieczeństwa; typ wyjątku nie został zmieniony."
        ]

    def _resolve_path(self, path_value: str) -> Path:
        candidate = Path(path_value)
        if not candidate.is_absolute():
            candidate = self.project_root / candidate
        return candidate.resolve()

    def _validate_path(self, file_path: Path) -> str:
        try:
            file_path.relative_to(self.project_root)
        except ValueError:
            return "Ścieżka znajduje się poza katalogiem projektu."
        return ""

    def _validate_file(self, file_path: Path) -> str:
        if self.policy.require_existing_file and not file_path.exists():
            return f"Plik nie istnieje: {file_path}"
        if not file_path.is_file():
            return f"Ścieżka nie jest plikiem: {file_path}"
        if (
            self.policy.require_python_file
            and file_path.suffix.casefold() != ".py"
        ):
            return "Generator obsługuje wyłącznie pliki Python."

        try:
            size = file_path.stat().st_size
        except OSError as error:
            return f"Nie udało się odczytać rozmiaru: {error}"

        if size > self.policy.max_file_size_bytes:
            return (
                "Plik przekracza limit rozmiaru "
                f"{self.policy.max_file_size_bytes} bajtów."
            )
        return ""

    def _syntax_error(self, content: str, file_path: Path) -> str:
        try:
            ast.parse(content, filename=str(file_path))
        except SyntaxError as error:
            return (
                "Błąd składni: "
                f"linia {error.lineno or 0}, {error.msg}"
            )
        return ""

    def _count_changed_lines(
        self,
        old_content: str,
        proposed_content: str,
    ) -> int:
        old_lines = old_content.splitlines()
        new_lines = proposed_content.splitlines()
        max_length = max(len(old_lines), len(new_lines))
        changed = 0

        for index in range(max_length):
            old_line = old_lines[index] if index < len(old_lines) else None
            new_line = new_lines[index] if index < len(new_lines) else None
            if old_line != new_line:
                changed += 1

        return changed

    def _hash(self, content: str) -> str:
        return hashlib.sha256(content.encode("utf-8")).hexdigest()

    def _safe_int(self, value: Any) -> int:
        try:
            return int(value)
        except (TypeError, ValueError):
            return 0

    def _finish(
        self,
        candidate: CodePatchCandidate,
    ) -> CodePatchCandidate:
        self.last_candidate = candidate
        return candidate

    def status(self) -> dict[str, Any]:
        return {
            "project_root": str(self.project_root),
            "generation_count": self.generation_count,
            "policy": asdict(self.policy),
            "last_candidate": (
                self.last_candidate.to_dict()
                if self.last_candidate is not None
                else None
            ),
        }
