from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class _Finding:
    title: str
    description: str
    target: str
    severity: str
    issue_type: str
    value_score: float
    risk_score: float
    effort_score: float
    confidence: float
    priority_score: float
    metadata: dict[str, Any]

    def to_candidate(self) -> dict[str, Any]:
        task = {
            "title": self.title,
            "description": self.description,
            "target": self.target,
            "severity": self.severity,
            "priority_score": self.priority_score,
            "recommendation": (
                "Wprowadź najmniejszą bezpieczną zmianę, "
                "zachowaj publiczne API i dodaj test regresyjny."
            ),
            "metadata": {
                **self.metadata,
                "issue_type": self.issue_type,
                "estimated_effort": self.effort_score,
                "confidence": self.confidence,
            },
        }
        final_score = round(
            self.value_score
            + self.confidence * 25.0
            - self.risk_score * 0.55
            - self.effort_score * 0.30,
            2,
        )
        return {
            "task": task,
            "predicted_risk": self.risk_score,
            "value_score": self.value_score,
            "effort_score": self.effort_score,
            "final_score": final_score,
            "decision": (
                "PREVIEW_ONLY"
                if self.risk_score > 65.0
                else "READY_FOR_SAFE_GENERATION"
            ),
        }


class ProjectOpportunityScanner:
    """Fast bounded AST scanner used by B55 background cycles."""

    IGNORED_DIRS = {
        ".git",
        ".idea",
        ".pytest_cache",
        ".venv",
        "AI_PLIKI",
        "archive",
        "backups",
        "build",
        "data",
        "dist",
        "env",
        "venv",
        "__pycache__",
    }

    def __init__(
        self,
        project_root: str | Path,
        *,
        max_files: int = 900,
        max_file_bytes: int = 750_000,
        max_opportunities: int = 100,
    ) -> None:
        self.project_root = Path(project_root).resolve(strict=False)
        self.max_files = min(5000, max(50, int(max_files)))
        self.max_file_bytes = min(
            5_000_000,
            max(50_000, int(max_file_bytes)),
        )
        self.max_opportunities = min(
            500,
            max(10, int(max_opportunities)),
        )

    def run_cycle(self) -> dict[str, Any]:
        findings: list[_Finding] = []
        errors: list[str] = []
        files_scanned = 0
        for path in self._iter_files():
            if files_scanned >= self.max_files:
                break
            files_scanned += 1
            try:
                findings.extend(self._inspect(path))
            except Exception as error:
                relative = self._relative(path)
                errors.append(
                    f"{relative}: {type(error).__name__}: {error}"
                )
        candidates = [
            item.to_candidate()
            for item in findings
        ]
        candidates.sort(
            key=lambda item: float(item.get("final_score", 0.0)),
            reverse=True,
        )
        candidates = candidates[: self.max_opportunities]
        return {
            "success": True,
            "status": "B55_PROJECT_SCAN_COMPLETED",
            "files_scanned": files_scanned,
            "errors": errors[:50],
            "prioritization": {
                "success": True,
                "status": (
                    "IMPROVEMENT_SELECTED"
                    if candidates
                    else "NO_CANDIDATES"
                ),
                "selected": candidates[0] if candidates else None,
                "candidates": candidates,
            },
        }

    def _iter_files(self):
        roots = [
            self.project_root / "app",
        ]
        for root in roots:
            if not root.is_dir():
                continue
            for path in root.rglob("*.py"):
                try:
                    parts = set(
                        path.relative_to(self.project_root).parts
                    )
                except ValueError:
                    continue
                if parts.intersection(self.IGNORED_DIRS):
                    continue
                try:
                    if path.stat().st_size > self.max_file_bytes:
                        continue
                except OSError:
                    continue
                yield path

    def _inspect(self, path: Path) -> list[_Finding]:
        relative = self._relative(path)
        source = path.read_text(encoding="utf-8")
        lines = source.splitlines()
        try:
            tree = ast.parse(source, filename=relative)
        except SyntaxError as error:
            return [
                _Finding(
                    title="Napraw błąd składni Python",
                    description=(
                        f"Parser wykrył błąd składni w linii "
                        f"{error.lineno or 0}: {error.msg}."
                    ),
                    target=relative,
                    severity="CRITICAL",
                    issue_type="SYNTAX_ERROR",
                    value_score=95.0,
                    risk_score=20.0,
                    effort_score=8.0,
                    confidence=1.0,
                    priority_score=100.0,
                    metadata={
                        "line": error.lineno or 0,
                        "offset": error.offset or 0,
                    },
                )
            ]

        findings: list[_Finding] = []
        line_count = len(lines)
        functions = [
            node
            for node in ast.walk(tree)
            if isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef),
            )
        ]
        classes = [
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
        ]
        broad_exceptions = sum(
            1
            for node in ast.walk(tree)
            if isinstance(node, ast.ExceptHandler)
            and (
                node.type is None
                or (
                    isinstance(node.type, ast.Name)
                    and node.type.id in {"Exception", "BaseException"}
                )
            )
        )
        branches = sum(
            1
            for node in ast.walk(tree)
            if isinstance(
                node,
                (
                    ast.If,
                    ast.For,
                    ast.AsyncFor,
                    ast.While,
                    ast.Try,
                    ast.Match,
                    ast.BoolOp,
                ),
            )
        )
        longest_function = 0
        longest_name = ""
        for node in functions:
            end = int(getattr(node, "end_lineno", node.lineno) or node.lineno)
            length = max(1, end - int(node.lineno) + 1)
            if length > longest_function:
                longest_function = length
                longest_name = node.name

        if line_count >= 650:
            findings.append(
                _Finding(
                    title="Podziel zbyt duży moduł",
                    description=(
                        f"Moduł ma {line_count} linii, "
                        f"{len(classes)} klas i {len(functions)} funkcji."
                    ),
                    target=relative,
                    severity="HIGH",
                    issue_type="LARGE_MODULE",
                    value_score=min(80.0, 45.0 + line_count / 80.0),
                    risk_score=58.0,
                    effort_score=30.0,
                    confidence=0.95,
                    priority_score=75.0,
                    metadata={
                        "line_count": line_count,
                        "function_count": len(functions),
                        "class_count": len(classes),
                    },
                )
            )
        elif line_count >= 400:
            findings.append(
                _Finding(
                    title="Przygotuj bezpieczny przegląd dużego modułu",
                    description=(
                        f"Moduł ma {line_count} linii. "
                        "Wskaż małe wydzielenie lub poprawę testowalności."
                    ),
                    target=relative,
                    severity="MEDIUM",
                    issue_type="MODULE_MAINTAINABILITY",
                    value_score=40.0,
                    risk_score=38.0,
                    effort_score=18.0,
                    confidence=0.85,
                    priority_score=55.0,
                    metadata={"line_count": line_count},
                )
            )

        if longest_function >= 120:
            findings.append(
                _Finding(
                    title="Podziel zbyt długą funkcję",
                    description=(
                        f"Funkcja {longest_name} ma "
                        f"{longest_function} linii."
                    ),
                    target=relative,
                    severity="HIGH",
                    issue_type="LONG_FUNCTION",
                    value_score=55.0,
                    risk_score=45.0,
                    effort_score=20.0,
                    confidence=0.95,
                    priority_score=70.0,
                    metadata={
                        "function": longest_name,
                        "function_lines": longest_function,
                    },
                )
            )
        elif longest_function >= 80:
            findings.append(
                _Finding(
                    title="Uprość długą funkcję",
                    description=(
                        f"Funkcja {longest_name} ma "
                        f"{longest_function} linii."
                    ),
                    target=relative,
                    severity="MEDIUM",
                    issue_type="LONG_FUNCTION",
                    value_score=40.0,
                    risk_score=35.0,
                    effort_score=14.0,
                    confidence=0.9,
                    priority_score=50.0,
                    metadata={
                        "function": longest_name,
                        "function_lines": longest_function,
                    },
                )
            )

        if broad_exceptions >= 4:
            findings.append(
                _Finding(
                    title="Zawęź zbyt szeroką obsługę wyjątków",
                    description=(
                        f"Moduł zawiera {broad_exceptions} szerokich "
                        "bloków except. Zachowaj istniejące zachowanie."
                    ),
                    target=relative,
                    severity="MEDIUM",
                    issue_type="BROAD_EXCEPTION",
                    value_score=38.0,
                    risk_score=28.0,
                    effort_score=10.0,
                    confidence=0.85,
                    priority_score=48.0,
                    metadata={
                        "broad_exception_count": broad_exceptions,
                    },
                )
            )

        todo_count = sum(
            1
            for line in lines
            if "TODO" in line.upper() or "FIXME" in line.upper()
        )
        if todo_count >= 2:
            findings.append(
                _Finding(
                    title="Uporządkuj zaległe TODO i FIXME",
                    description=(
                        f"Moduł zawiera {todo_count} znaczników "
                        "TODO/FIXME wymagających bezpiecznej analizy."
                    ),
                    target=relative,
                    severity="LOW",
                    issue_type="TODO_DEBT",
                    value_score=25.0,
                    risk_score=18.0,
                    effort_score=8.0,
                    confidence=0.75,
                    priority_score=35.0,
                    metadata={"todo_count": todo_count},
                )
            )

        if branches >= 90 and line_count >= 250:
            findings.append(
                _Finding(
                    title="Zmniejsz złożoność sterowania modułu",
                    description=(
                        f"Analiza AST wykryła {branches} punktów "
                        "decyzyjnych w module."
                    ),
                    target=relative,
                    severity="MEDIUM",
                    issue_type="HIGH_BRANCH_COMPLEXITY",
                    value_score=45.0,
                    risk_score=42.0,
                    effort_score=22.0,
                    confidence=0.85,
                    priority_score=58.0,
                    metadata={"branch_nodes": branches},
                )
            )
        return findings

    def _relative(self, path: Path) -> str:
        return path.resolve(strict=False).relative_to(
            self.project_root
        ).as_posix()
