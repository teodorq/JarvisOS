import ast
from pathlib import Path


class CodeGenerator:

    def generate_file_replacement(
        self,
        path: str,
        instruction: str,
        proposed_content: str
    ) -> dict:

        file_path = Path(path)

        result = {
            "success": False,
            "path": str(file_path),
            "instruction": instruction,
            "old_content": "",
            "new_content": proposed_content,
            "errors": []
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
            proposed_content
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
        new_function_code: str
    ) -> dict:

        file_path = Path(path)

        result = {
            "success": False,
            "path": str(file_path),
            "function_name": function_name,
            "old_content": "",
            "new_content": "",
            "old_function": "",
            "new_function": new_function_code,
            "errors": []
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
                        ast.AsyncFunctionDef
                    )
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
            None
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
            new_function_code
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
            new_content
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

    def _match_indentation(
        self,
        old_code: str,
        new_code: str
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
        lines: list[str]
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
        content: str
    ) -> str:

        if file_path.suffix.lower() != ".py":
            return ""

        try:
            ast.parse(
                content,
                filename=str(file_path)
            )

            return ""

        except SyntaxError as error:
            return (
                "Błąd składni w proponowanym kodzie: "
                f"linia {error.lineno}, "
                f"kolumna {error.offset}: "
                f"{error.msg}"
            )