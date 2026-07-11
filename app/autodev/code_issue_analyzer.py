from __future__ import annotations

import ast
from pathlib import Path
from typing import Any


class CodeIssueAnalyzer:

    def __init__(self) -> None:

        self.last_result: dict[str, Any] | None = None

    def analyze(
        self,
        target: dict[str, Any],
    ) -> dict[str, Any]:

        path_value = str(
            target.get(
                "path",
                "",
            )
        ).strip()

        file_path = Path(
            path_value
        )

        if not file_path.exists():
            result = {
                "success": False,
                "status": "FILE_NOT_FOUND",
                "path": path_value,
                "issues": [],
            }

            self.last_result = result
            return result

        try:
            content = file_path.read_text(
                encoding="utf-8"
            )
        except Exception as error:
            result = {
                "success": False,
                "status": "READ_FAILED",
                "path": str(
                    file_path
                ),
                "issues": [],
                "error": (
                    f"{type(error).__name__}: {error}"
                ),
            }

            self.last_result = result
            return result

        issues: list[dict[str, Any]] = []

        issues.extend(
            self._analyze_text(
                content
            )
        )

        issues.extend(
            self._analyze_ast(
                content=content,
                path=file_path,
            )
        )

        issues.sort(
            key=lambda item: (
                -int(
                    item.get(
                        "score",
                        0,
                    )
                ),
                int(
                    item.get(
                        "line",
                        0,
                    )
                ),
            )
        )

        result = {
            "success": True,
            "status": "ANALYSIS_COMPLETED",
            "path": str(
                file_path
            ),
            "issues_count": len(
                issues
            ),
            "issues": issues,
        }

        self.last_result = result
        return result

    def _analyze_text(
        self,
        content: str,
    ) -> list[dict[str, Any]]:

        issues: list[dict[str, Any]] = []

        for line_number, line in enumerate(
            content.splitlines(),
            start=1,
        ):
            stripped = line.strip()
            lowered = stripped.casefold()

            if "todo" in lowered:
                issues.append(
                    {
                        "type": "TODO",
                        "severity": "NORMAL",
                        "score": 30,
                        "line": line_number,
                        "message": (
                            "Wykryto niedokończone TODO."
                        ),
                    }
                )

            if stripped == "pass":
                issues.append(
                    {
                        "type": "EMPTY_BLOCK",
                        "severity": "HIGH",
                        "score": 50,
                        "line": line_number,
                        "message": (
                            "Wykryto pusty blok pass."
                        ),
                    }
                )

            if (
                stripped.startswith(
                    "except Exception"
                )
                and stripped.endswith(
                    ":"
                )
            ):
                issues.append(
                    {
                        "type": "BROAD_EXCEPTION",
                        "severity": "LOW",
                        "score": 15,
                        "line": line_number,
                        "message": (
                            "Wykryto szeroką obsługę Exception."
                        ),
                    }
                )

    def _analyze_ast(
        self,
        *,
        content: str,
        path: Path,
    ) -> list[dict[str, Any]]:

        try:
            tree = ast.parse(
                content,
                filename=str(
                    path
                ),
            )
        except SyntaxError as error:
            return [
                {
                    "type": "SYNTAX_ERROR",
                    "severity": "CRITICAL",
                    "score": 100,
                    "line": error.lineno or 0,
                    "message": str(
                        error
                    ),
                }
            ]

        issues: list[dict[str, Any]] = []

        for node in ast.walk(
            tree
        ):
            if isinstance(
                node,
                ast.FunctionDef,
            ):
                function_lines = (
                    getattr(
                        node,
                        "end_lineno",
                        node.lineno,
                    )
                    - node.lineno
                    + 1
                )

                if function_lines > 120:
                    issues.append(
                        {
                            "type": "LONG_FUNCTION",
                            "severity": "NORMAL",
                            "score": 25,
                            "line": node.lineno,
                            "function": node.name,
                            "message": (
                                f"Funkcja {node.name} "
                                f"ma {function_lines} linii."
                            ),
                        }
                    )

                if len(
                    node.args.args
                ) > 8:
                    issues.append(
                        {
                            "type": "TOO_MANY_ARGUMENTS",
                            "severity": "LOW",
                            "score": 10,
                            "line": node.lineno,
                            "function": node.name,
                            "message": (
                                f"Funkcja {node.name} ma "
                                f"{len(node.args.args)} argumentów."
                            ),
                        }
                    )

            if isinstance(
                node,
                ast.ClassDef,
            ):
                class_lines = (
                    getattr(
                        node,
                        "end_lineno",
                        node.lineno,
                    )
                    - node.lineno
                    + 1
                )

                if class_lines > 500:
                    issues.append(
                        {
                            "type": "LARGE_CLASS",
                            "severity": "NORMAL",
                            "score": 35,
                            "line": node.lineno,
                            "class": node.name,
                            "message": (
                                f"Klasa {node.name} "
                                f"ma {class_lines} linii."
                            ),
                        }
                    )

        return issues

    def best_issue(
        self,
    ) -> dict[str, Any] | None:

        if not self.last_result:
            return None

        issues = self.last_result.get(
            "issues",
            [],
        )

        if not issues:
            return None

        return dict(
            issues[0]
        )

    def status(
        self,
    ) -> dict[str, Any]:

        return {
            "last_result": self.last_result,
            "best_issue": self.best_issue(),
        }