from app.core.project_paths import (
    default_project_path,
    default_project_root,
)

import ast
from pathlib import Path
from typing import Any


class CodeGenerator:

    def __init__(
        self,
        project_root: str = default_project_root(),
    ) -> None:
        self.project_root = Path(project_root)

    def generate_autonomous_file_improvement(
        self,
        path: str,
        instruction: str = "",
    ) -> dict[str, Any]:

        file_path = self._resolve_path(path)

        result: dict[str, Any] = {
            "success": False,
            "path": str(file_path),
            "instruction": instruction,
            "old_content": "",
            "new_content": "",
            "strategy": "",
            "errors": [],
        }

        if not file_path.exists():
            result["errors"].append(
                f"Plik nie istnieje: {file_path}"
            )
            return result

        if not file_path.is_file():
            result["errors"].append(
                f"Ścieżka nie jest plikiem: {file_path}"
            )
            return result

        if file_path.suffix.casefold() != ".py":
            result["errors"].append(
                "Autonomiczny generator obsługuje "
                "obecnie wyłącznie pliki Python."
            )
            return result

        try:
            old_content = file_path.read_text(
                encoding="utf-8"
            )
        except Exception as error:
            result["errors"].append(
                f"Nie udało się odczytać pliku: {error}"
            )
            return result

        result["old_content"] = old_content

        syntax_error = self._check_python_syntax(
            file_path,
            old_content,
        )

        if syntax_error:
            result["errors"].append(
                "Plik źródłowy ma błąd składni. "
                + syntax_error
            )
            return result

        new_content, strategy = (
            self._safe_python_improvement(
                old_content
            )
        )

        if new_content == old_content:
            result["errors"].append(
                "Nie znaleziono bezpiecznej, "
                "deterministycznej zmiany dla pliku."
            )
            return result

        syntax_error = self._check_python_syntax(
            file_path,
            new_content,
        )

        if syntax_error:
            result["errors"].append(
                syntax_error
            )
            return result

        result["success"] = True
        result["new_content"] = new_content
        result["strategy"] = strategy
        return result

    def generate_file_replacement(
        self,
        path: str,
        instruction: str,
        proposed_content: str,
    ) -> dict:

        file_path = self._resolve_path(path)

        result = {
            "success": False,
            "path": str(file_path),
            "instruction": instruction,
            "old_content": "",
            "new_content": proposed_content,
            "errors": [],
        }

        if not file_path.exists():
            result["errors"].append(
                f"Plik nie istnieje: {file_path}"
            )
            return result

        try:
            old_content = file_path.read_text(
                encoding="utf-8"
            )
            result["old_content"] = old_content
        except Exception as error:
            result["errors"].append(
                f"Nie udało się odczytać pliku: {error}"
            )
            return result

        if old_content == proposed_content:
            result["errors"].append(
                "Nowa zawartość jest identyczna "
                "z obecną zawartością."
            )
            return result

        syntax_error = self._check_python_syntax(
            file_path,
            proposed_content,
        )

        if syntax_error:
            result["errors"].append(
                syntax_error
            )
            return result

        result["success"] = True
        return result

    def generate_function_replacement(
        self,
        path: str,
        function_name: str,
        new_function_code: str,
    ) -> dict:

        file_path = self._resolve_path(path)

        result = {
            "success": False,
            "path": str(file_path),
            "function_name": function_name,
            "old_content": "",
            "new_content": "",
            "old_function": "",
            "new_function": new_function_code,
            "errors": [],
        }

        if not file_path.exists():
            result["errors"].append(
                f"Plik nie istnieje: {file_path}"
            )
            return result

        try:
            source = file_path.read_text(
                encoding="utf-8"
            )
            tree = ast.parse(source)
            lines = source.splitlines()
        except Exception as error:
            result["errors"].append(
                f"Nie udało się odczytać kodu: {error}"
            )
            return result

        target_node = None

        for node in ast.walk(tree):
            if (
                isinstance(
                    node,
                    (
                        ast.FunctionDef,
                        ast.AsyncFunctionDef,
                    ),
                )
                and node.name == function_name
            ):
                target_node = node
                break

        if target_node is None:
            result["errors"].append(
                f"Nie znaleziono funkcji: {function_name}"
            )
            return result

        end_line = getattr(
            target_node,
            "end_lineno",
            None,
        )

        if end_line is None:
            result["errors"].append(
                "Nie udało się ustalić końca funkcji."
            )
            return result

        start_line = target_node.lineno

        old_function = "\n".join(
            lines[start_line - 1:end_line]
        )

        new_function_code = self._match_indentation(
            old_function,
            new_function_code,
        )

        new_lines = (
            lines[:start_line - 1]
            + new_function_code.splitlines()
            + lines[end_line:]
        )

        new_content = "\n".join(new_lines)

        if source.endswith("\n"):
            new_content += "\n"

        syntax_error = self._check_python_syntax(
            file_path,
            new_content,
        )

        if syntax_error:
            result["errors"].append(
                syntax_error
            )
            return result

        result["success"] = True
        result["old_content"] = source
        result["new_content"] = new_content
        result["old_function"] = old_function
        result["new_function"] = new_function_code
        return result

    def _safe_python_improvement(
        self,
        content: str,
    ) -> tuple[str, str]:

        tree = ast.parse(content)

        has_future_annotations = any(
            isinstance(node, ast.ImportFrom)
            and node.module == "__future__"
            and any(
                alias.name == "annotations"
                for alias in node.names
            )
            for node in tree.body
        )

        if not has_future_annotations:
            lines = content.splitlines(
                keepends=True
            )
            insert_index = 0

            if lines and lines[0].startswith("#!"):
                insert_index = 1

            if tree.body:
                first_node = tree.body[0]

                if (
                    isinstance(
                        first_node,
                        ast.Expr,
                    )
                    and isinstance(
                        first_node.value,
                        (
                            ast.Str,
                            ast.Constant,
                        ),
                    )
                    and isinstance(
                        getattr(
                            first_node.value,
                            "value",
                            None,
                        ),
                        str,
                    )
                ):
                    insert_index = max(
                        insert_index,
                        int(
                            getattr(
                                first_node,
                                "end_lineno",
                                first_node.lineno,
                            )
                        ),
                    )

            lines.insert(
                insert_index,
                "from __future__ import annotations\n",
            )

            return (
                "".join(lines),
                "add_future_annotations",
            )

        if content and not content.endswith("\n"):
            return (
                content + "\n",
                "ensure_final_newline",
            )

        module_docstring = ast.get_docstring(
            tree,
            clean=False,
        )

        if module_docstring is None:
            return (
                (
                    '"""Moduł JARVIS OS utrzymywany '
                    'przez bezpieczny AutoDev."""\n\n'
                    + content
                ),
                "add_module_docstring",
            )

        return (
            content,
            "no_safe_change",
        )

    def _resolve_path(
        self,
        path: str,
    ) -> Path:

        file_path = Path(path)

        if file_path.is_absolute():
            return file_path

        return self.project_root / file_path

    def _match_indentation(
        self,
        old_code: str,
        new_code: str,
    ) -> str:

        old_lines = old_code.splitlines()

        if not old_lines:
            return new_code.strip("\n")

        first_line = old_lines[0]
        indentation = first_line[
            :len(first_line) - len(first_line.lstrip())
        ]

        new_lines = new_code.strip("\n").splitlines()

        if not new_lines:
            return new_code

        minimum_indent = self._minimum_indent(
            new_lines
        )

        normalized = []

        for line in new_lines:
            if not line.strip():
                normalized.append("")
                continue

            if minimum_indent > 0:
                line = line[minimum_indent:]

            normalized.append(
                indentation + line
            )

        return "\n".join(normalized)

    def _minimum_indent(
        self,
        lines: list[str],
    ) -> int:

        values = []

        for line in lines:
            if not line.strip():
                continue

            indent = (
                len(line)
                - len(line.lstrip())
            )
            values.append(indent)

        if not values:
            return 0

        return min(values)

    def _check_python_syntax(
        self,
        file_path: Path,
        content: str,
    ) -> str:

        if file_path.suffix.lower() != ".py":
            return ""

        try:
            ast.parse(
                content,
                filename=str(file_path),
            )
            return ""
        except SyntaxError as error:
            return (
                "Błąd składni w proponowanym kodzie: "
                f"linia {error.lineno}, "
                f"kolumna {error.offset}: "
                f"{error.msg}"
            )
