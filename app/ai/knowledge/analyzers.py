from __future__ import annotations

import ast
import hashlib
from collections import defaultdict
from pathlib import Path

from .models import CodeIssue


class ProjectQualityAnalyzer:
    def __init__(
        self,
        large_file_lines: int = 700,
        complex_function_branches: int = 12,
        duplicate_min_statements: int = 4,
    ) -> None:
        self.large_file_lines = large_file_lines
        self.complex_function_branches = complex_function_branches
        self.duplicate_min_statements = duplicate_min_statements

    def analyze(
        self,
        project_root: str | Path,
        code_map: dict[str, dict],
    ) -> list[CodeIssue]:
        root = Path(project_root).resolve()
        issues: list[CodeIssue] = []
        issues.extend(self._large_files(code_map))
        issues.extend(self._parse_errors(code_map))
        issues.extend(self._missing_tests(root, code_map))
        issues.extend(self._complexity(root, code_map))
        issues.extend(self._duplicate_functions(root, code_map))
        issues.extend(self._dead_private_functions(root, code_map))
        return issues

    def _large_files(self, code_map: dict[str, dict]) -> list[CodeIssue]:
        result: list[CodeIssue] = []
        for path, data in code_map.items():
            line_count = int(data.get("line_count", 0))
            if line_count > self.large_file_lines:
                result.append(
                    CodeIssue(
                        category="large_file",
                        path=path,
                        message=f"Plik ma {line_count} linii i powinien zostać podzielony.",
                        severity="medium",
                        evidence={"line_count": line_count, "threshold": self.large_file_lines},
                    )
                )
        return result

    @staticmethod
    def _parse_errors(code_map: dict[str, dict]) -> list[CodeIssue]:
        return [
            CodeIssue(
                category="parse_error",
                path=path,
                message="Nie udało się przeanalizować pliku Python.",
                severity="high",
                evidence={"error": data["parse_error"]},
            )
            for path, data in code_map.items()
            if data.get("parse_error")
        ]

    @staticmethod
    def _missing_tests(root: Path, code_map: dict[str, dict]) -> list[CodeIssue]:
        test_names = {
            Path(path).stem.removeprefix("test_")
            for path in code_map
            if path.startswith("tests/") or "/tests/" in path
        }
        result: list[CodeIssue] = []
        for path, data in code_map.items():
            if path.startswith("tests/") or "/tests/" in path or path.endswith("/__init__.py"):
                continue
            stem = Path(path).stem
            has_public_api = bool(data.get("classes") or [f for f in data.get("functions", []) if not f.startswith("_")])
            if has_public_api and stem not in test_names:
                result.append(
                    CodeIssue(
                        category="missing_test",
                        path=path,
                        message="Moduł ma publiczne API, ale nie znaleziono pasującego testu.",
                        severity="high",
                        evidence={"expected_pattern": f"test_{stem}.py"},
                    )
                )
        return result

    def _complexity(self, root: Path, code_map: dict[str, dict]) -> list[CodeIssue]:
        result: list[CodeIssue] = []
        branch_nodes = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With, ast.AsyncWith, ast.Match)
        for relative in code_map:
            path = root / relative
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (OSError, UnicodeDecodeError, SyntaxError):
                continue
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    branch_count = sum(isinstance(child, branch_nodes) for child in ast.walk(node))
                    if branch_count > self.complex_function_branches:
                        result.append(
                            CodeIssue(
                                category="high_complexity",
                                path=relative,
                                line=node.lineno,
                                message=f"Funkcja {node.name} ma zbyt wiele rozgałęzień ({branch_count}).",
                                severity="medium",
                                evidence={"function": node.name, "branch_count": branch_count},
                            )
                        )
        return result

    def _duplicate_functions(self, root: Path, code_map: dict[str, dict]) -> list[CodeIssue]:
        fingerprints: dict[str, list[tuple[str, str, int]]] = defaultdict(list)
        for relative in code_map:
            path = root / relative
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            except (OSError, UnicodeDecodeError, SyntaxError):
                continue
            for node in ast.walk(tree):
                if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    continue
                if len(node.body) < self.duplicate_min_statements:
                    continue
                normalized = ast.dump(ast.Module(body=node.body, type_ignores=[]), include_attributes=False)
                digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
                fingerprints[digest].append((relative, node.name, node.lineno))

        result: list[CodeIssue] = []
        for matches in fingerprints.values():
            if len(matches) < 2:
                continue
            locations = [f"{path}:{line} ({name})" for path, name, line in matches]
            for path, name, line in matches:
                result.append(
                    CodeIssue(
                        category="duplicate_code",
                        path=path,
                        line=line,
                        message=f"Funkcja {name} ma duplikat w innym miejscu projektu.",
                        severity="medium",
                        evidence={"locations": locations},
                    )
                )
        return result

    @staticmethod
    def _dead_private_functions(root: Path, code_map: dict[str, dict]) -> list[CodeIssue]:
        result: list[CodeIssue] = []
        for relative in code_map:
            path = root / relative
            try:
                source = path.read_text(encoding="utf-8")
                tree = ast.parse(source, filename=str(path))
            except (OSError, UnicodeDecodeError, SyntaxError):
                continue
            names = [
                node.name
                for node in ast.walk(tree)
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name.startswith("_")
                and not node.name.startswith("__")
            ]
            for name in names:
                if source.count(name) == 1:
                    result.append(
                        CodeIssue(
                            category="possible_dead_code",
                            path=relative,
                            message=f"Prywatna funkcja {name} nie jest używana w swoim module.",
                            severity="low",
                            evidence={"function": name},
                        )
                    )
        return result
