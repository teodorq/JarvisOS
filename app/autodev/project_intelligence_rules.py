from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from app.autodev.module_analysis import ModuleAnalysis


@dataclass(slots=True)
class RuleFinding:
    module: str
    severity: str
    title: str
    description: str
    recommendation: str
    score: float
    metadata: dict[str, Any]


class IntelligenceRule(Protocol):
    name: str

    def detect(
        self,
        analysis: ModuleAnalysis,
        source: str,
        tree: ast.AST,
    ) -> list[RuleFinding]:
        ...


class TodoCommentRule:
    name = "todo_comment"
    KEYWORDS = ("TODO", "FIXME", "XXX", "HACK")

    def detect(self, analysis, source, tree):
        findings = []
        for line_number, line in enumerate(
            source.splitlines(),
            start=1,
        ):
            stripped = line.strip()
            if not stripped.startswith("#"):
                continue

            keyword = next(
                (
                    item
                    for item in self.KEYWORDS
                    if item in stripped.upper()
                ),
                None,
            )
            if keyword is None:
                continue

            findings.append(
                RuleFinding(
                    module=analysis.path,
                    severity="LOW",
                    title=f"Komentarz {keyword}",
                    description=(
                        f"W linii {line_number} znaleziono "
                        f"komentarz {keyword}."
                    ),
                    recommendation=(
                        "Zweryfikuj komentarz i zamień go "
                        "na konkretne zadanie albo usuń."
                    ),
                    score=4.0,
                    metadata={
                        "rule": self.name,
                        "line": line_number,
                        "keyword": keyword,
                        "excerpt": stripped[:200],
                    },
                )
            )
        return findings


class LongFunctionRule:
    name = "long_function"

    def __init__(self, max_lines: int = 80):
        self.max_lines = max_lines

    def detect(self, analysis, source, tree):
        findings = []
        for node in ast.walk(tree):
            if not isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef),
            ):
                continue

            end_line = getattr(node, "end_lineno", None)
            if end_line is None:
                continue

            length = end_line - node.lineno + 1
            if length <= self.max_lines:
                continue

            severity = "HIGH" if length > 160 else "MEDIUM"
            findings.append(
                RuleFinding(
                    module=analysis.path,
                    severity=severity,
                    title="Zbyt długa funkcja",
                    description=(
                        f"Funkcja {node.name} ma {length} linii."
                    ),
                    recommendation=(
                        "Podziel funkcję na mniejsze operacje."
                    ),
                    score=9.0 if severity == "HIGH" else 7.0,
                    metadata={
                        "rule": self.name,
                        "function_name": node.name,
                        "line": node.lineno,
                        "length": length,
                    },
                )
            )
        return findings


class EmptyExceptRule:
    name = "empty_except"

    def detect(self, analysis, source, tree):
        findings = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue

            body = list(node.body)
            is_empty = (
                not body
                or all(isinstance(item, ast.Pass) for item in body)
            )
            if not is_empty:
                continue

            findings.append(
                RuleFinding(
                    module=analysis.path,
                    severity="HIGH",
                    title="Pusty blok except",
                    description=(
                        f"Blok except w linii {node.lineno} "
                        "ignoruje błąd."
                    ),
                    recommendation=(
                        "Dodaj logowanie lub obsługę błędu."
                    ),
                    score=9.2,
                    metadata={
                        "rule": self.name,
                        "line": node.lineno,
                    },
                )
            )
        return findings


class BareExceptRule:
    name = "bare_except"

    def detect(self, analysis, source, tree):
        findings = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue
            if node.type is not None:
                continue

            findings.append(
                RuleFinding(
                    module=analysis.path,
                    severity="MEDIUM",
                    title="Zbyt szeroki except",
                    description=(
                        f"Blok except w linii {node.lineno} "
                        "przechwytuje wszystkie wyjątki."
                    ),
                    recommendation=(
                        "Przechwytuj konkretne typy wyjątków."
                    ),
                    score=7.5,
                    metadata={
                        "rule": self.name,
                        "line": node.lineno,
                    },
                )
            )
        return findings


class PassOnlyFunctionRule:
    name = "pass_only_function"

    def detect(self, analysis, source, tree):
        findings = []
        for node in ast.walk(tree):
            if not isinstance(
                node,
                (ast.FunctionDef, ast.AsyncFunctionDef),
            ):
                continue
            if len(node.body) != 1:
                continue
            if not isinstance(node.body[0], ast.Pass):
                continue

            findings.append(
                RuleFinding(
                    module=analysis.path,
                    severity="LOW",
                    title="Pusta funkcja",
                    description=(
                        f"Funkcja {node.name} zawiera tylko pass."
                    ),
                    recommendation=(
                        "Zaimplementuj funkcję albo oznacz ją "
                        "jako abstrakcyjną."
                    ),
                    score=4.5,
                    metadata={
                        "rule": self.name,
                        "function_name": node.name,
                        "line": node.lineno,
                    },
                )
            )
        return findings


class MissingModuleDocstringRule:
    name = "missing_module_docstring"

    def detect(self, analysis, source, tree):
        if ast.get_docstring(tree, clean=False):
            return []

        return [
            RuleFinding(
                module=analysis.path,
                severity="LOW",
                title="Brak opisu modułu",
                description=(
                    "Moduł nie posiada docstringa."
                ),
                recommendation=(
                    "Dodaj krótki docstring modułu."
                ),
                score=3.0,
                metadata={"rule": self.name},
            )
        ]


class ProjectIntelligenceRuleEngine:

    def __init__(self, rules=None):
        self.rules = rules or [
            EmptyExceptRule(),
            BareExceptRule(),
            LongFunctionRule(),
            PassOnlyFunctionRule(),
            TodoCommentRule(),
            MissingModuleDocstringRule(),
        ]

    def detect(
        self,
        analysis: ModuleAnalysis,
    ) -> list[RuleFinding]:

        file_path = Path(analysis.path)
        if not file_path.exists():
            return []

        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(
                source,
                filename=str(file_path),
            )
        except Exception:
            return []

        findings = []
        for rule in self.rules:
            findings.extend(
                rule.detect(analysis, source, tree)
            )

        return findings
