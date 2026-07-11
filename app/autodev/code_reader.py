import ast
from pathlib import Path
from typing import Any


class CodeReader:

    def __init__(
        self,
        project_root: str = "C:/JarvisAI"
    ):
        self.project_root = Path(
            project_root
        ).resolve()

    def read(
        self,
        path: str
    ) -> dict[str, Any]:

        file_path = self._resolve_path(
            path
        )

        result = {
            "success": False,
            "path": str(file_path),
            "relative_path": "",
            "content": "",
            "size": 0,
            "line_count": 0,
            "imports": [],
            "classes": [],
            "functions": [],
            "async_functions": [],
            "methods": [],
            "constants": [],
            "docstring": "",
            "errors": []
        }

        if not self._is_inside_project(
            file_path
        ):
            result["errors"].append(
                "Plik znajduje się poza katalogiem projektu."
            )

            return result

        if not file_path.exists():
            result["errors"].append(
                f"Plik nie istnieje: {file_path}"
            )

            return result

        if not file_path.is_file():
            result["errors"].append(
                f"Ścieżka nie wskazuje pliku: {file_path}"
            )

            return result

        try:
            content = file_path.read_text(
                encoding="utf-8"
            )

        except UnicodeDecodeError:
            try:
                content = file_path.read_text(
                    encoding="utf-8-sig"
                )

            except Exception as error:
                result["errors"].append(
                    "Nie udało się odczytać pliku: "
                    f"{error}"
                )

                return result

        except Exception as error:
            result["errors"].append(
                "Nie udało się odczytać pliku: "
                f"{error}"
            )

            return result

        result["content"] = content
        result["size"] = len(
            content.encode(
                "utf-8"
            )
        )

        result["line_count"] = len(
            content.splitlines()
        )

        try:
            result["relative_path"] = str(
                file_path.relative_to(
                    self.project_root
                )
            )

        except ValueError:
            result["relative_path"] = str(
                file_path
            )

        if file_path.suffix.lower() != ".py":
            result["success"] = True
            return result

        try:
            tree = ast.parse(
                content,
                filename=str(file_path)
            )

        except SyntaxError as error:
            result["errors"].append(
                "Błąd składni: "
                f"linia {error.lineno}, "
                f"kolumna {error.offset}: "
                f"{error.msg}"
            )

            return result

        except Exception as error:
            result["errors"].append(
                "Nie udało się przeanalizować AST: "
                f"{error}"
            )

            return result

        result["docstring"] = (
            ast.get_docstring(tree)
            or ""
        )

        class_stack = []

        for node in tree.body:
            self._collect_node(
                node=node,
                result=result,
                class_stack=class_stack
            )

        result["success"] = True

        return result

    def read_many(
        self,
        paths: list[str],
        max_files: int = 100
    ) -> list[dict[str, Any]]:

        results = []
        seen = set()

        for raw_path in paths:
            if len(results) >= max_files:
                break

            normalized = str(
                self._resolve_path(
                    raw_path
                )
            )

            if normalized in seen:
                continue

            seen.add(
                normalized
            )

            results.append(
                self.read(
                    normalized
                )
            )

        return results

    def extract_snippet(
        self,
        path: str,
        start_line: int,
        end_line: int
    ) -> dict[str, Any]:

        file_data = self.read(
            path
        )

        if not file_data.get(
            "success",
            False
        ):
            return {
                "success": False,
                "path": file_data.get(
                    "path",
                    path
                ),
                "start_line": start_line,
                "end_line": end_line,
                "content": "",
                "errors": file_data.get(
                    "errors",
                    []
                )
            }

        lines = file_data[
            "content"
        ].splitlines()

        if start_line < 1:
            start_line = 1

        if end_line < start_line:
            end_line = start_line

        if start_line > len(lines):
            return {
                "success": False,
                "path": file_data["path"],
                "start_line": start_line,
                "end_line": end_line,
                "content": "",
                "errors": [
                    "Linia początkowa jest poza plikiem."
                ]
            }

        selected = lines[
            start_line - 1:end_line
        ]

        return {
            "success": True,
            "path": file_data["path"],
            "start_line": start_line,
            "end_line": min(
                end_line,
                len(lines)
            ),
            "content": "\n".join(
                selected
            ),
            "errors": []
        }

    def find_symbol(
        self,
        path: str,
        symbol_name: str
    ) -> dict[str, Any]:

        file_data = self.read(
            path
        )

        result = {
            "success": False,
            "path": file_data.get(
                "path",
                path
            ),
            "symbol": symbol_name,
            "matches": [],
            "errors": []
        }

        if not file_data.get(
            "success",
            False
        ):
            result["errors"] = file_data.get(
                "errors",
                []
            )

            return result

        symbol_lower = (
            symbol_name
            .strip()
            .lower()
        )

        collections = [
            (
                "class",
                file_data["classes"]
            ),
            (
                "function",
                file_data["functions"]
            ),
            (
                "async_function",
                file_data["async_functions"]
            ),
            (
                "method",
                file_data["methods"]
            ),
            (
                "constant",
                file_data["constants"]
            )
        ]

        for symbol_type, items in collections:
            for item in items:
                name = str(
                    item.get(
                        "name",
                        ""
                    )
                )

                qualified_name = str(
                    item.get(
                        "qualified_name",
                        name
                    )
                )

                if (
                    symbol_lower in name.lower()
                    or symbol_lower
                    in qualified_name.lower()
                ):
                    result["matches"].append({
                        "type": symbol_type,
                        **item
                    })

        result["success"] = True

        return result

    def summary(
        self,
        path: str
    ) -> str:

        result = self.read(
            path
        )

        if not result.get(
            "success",
            False
        ):
            lines = [
                "CODE READER",
                f"Plik: {result.get('path', path)}",
                "Status: FAILED",
                ""
            ]

            for error in result.get(
                "errors",
                []
            ):
                lines.append(
                    f"- {error}"
                )

            return "\n".join(
                lines
            )

        return "\n".join([
            "CODE READER",
            f"Plik: {result['relative_path']}",
            "Status: SUCCESS",
            f"Rozmiar: {result['size']} B",
            f"Linie: {result['line_count']}",
            f"Importy: {len(result['imports'])}",
            f"Klasy: {len(result['classes'])}",
            f"Funkcje: {len(result['functions'])}",
            (
                "Funkcje async: "
                f"{len(result['async_functions'])}"
            ),
            f"Metody: {len(result['methods'])}",
            f"Stałe: {len(result['constants'])}"
        ])

    def _resolve_path(
        self,
        path: str
    ) -> Path:

        file_path = Path(
            path
        )

        if not file_path.is_absolute():
            file_path = (
                self.project_root
                / file_path
            )

        return file_path.resolve()

    def _is_inside_project(
        self,
        path: Path
    ) -> bool:

        try:
            path.relative_to(
                self.project_root
            )

            return True

        except ValueError:
            return False

    def _collect_node(
        self,
        node: ast.AST,
        result: dict[str, Any],
        class_stack: list[str]
    ):

        if isinstance(
            node,
            ast.Import
        ):
            for alias in node.names:
                result["imports"].append({
                    "module": alias.name,
                    "name": alias.name,
                    "alias": alias.asname or "",
                    "line": getattr(
                        node,
                        "lineno",
                        0
                    )
                })

            return

        if isinstance(
            node,
            ast.ImportFrom
        ):
            module_name = (
                node.module
                or ""
            )

            for alias in node.names:
                full_name = (
                    f"{module_name}.{alias.name}"
                    if module_name
                    else alias.name
                )

                result["imports"].append({
                    "module": module_name,
                    "name": full_name,
                    "alias": alias.asname or "",
                    "level": node.level,
                    "line": getattr(
                        node,
                        "lineno",
                        0
                    )
                })

            return

        if isinstance(
            node,
            ast.ClassDef
        ):
            qualified_name = ".".join(
                class_stack + [
                    node.name
                ]
            )

            result["classes"].append({
                "name": node.name,
                "qualified_name": qualified_name,
                "line": node.lineno,
                "end_line": getattr(
                    node,
                    "end_lineno",
                    node.lineno
                ),
                "bases": [
                    self._node_name(
                        base
                    )
                    for base in node.bases
                ],
                "docstring": (
                    ast.get_docstring(node)
                    or ""
                )
            })

            new_stack = (
                class_stack
                + [node.name]
            )

            for child in node.body:
                self._collect_node(
                    node=child,
                    result=result,
                    class_stack=new_stack
                )

            return

        if isinstance(
            node,
            ast.AsyncFunctionDef
        ):
            self._collect_function(
                node=node,
                result=result,
                class_stack=class_stack,
                is_async=True
            )

            return

        if isinstance(
            node,
            ast.FunctionDef
        ):
            self._collect_function(
                node=node,
                result=result,
                class_stack=class_stack,
                is_async=False
            )

            return

        if isinstance(
            node,
            ast.Assign
        ):
            if class_stack:
                return

            for target in node.targets:
                if isinstance(
                    target,
                    ast.Name
                ):
                    if target.id.isupper():
                        result[
                            "constants"
                        ].append({
                            "name": target.id,
                            "qualified_name": target.id,
                            "line": node.lineno
                        })

            return

        if isinstance(
            node,
            ast.AnnAssign
        ):
            if class_stack:
                return

            if isinstance(
                node.target,
                ast.Name
            ):
                name = node.target.id

                if name.isupper():
                    result[
                        "constants"
                    ].append({
                        "name": name,
                        "qualified_name": name,
                        "line": node.lineno
                    })

    def _collect_function(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        result: dict[str, Any],
        class_stack: list[str],
        is_async: bool
    ):

        qualified_name = ".".join(
            class_stack + [
                node.name
            ]
        )

        item = {
            "name": node.name,
            "qualified_name": qualified_name,
            "line": node.lineno,
            "end_line": getattr(
                node,
                "end_lineno",
                node.lineno
            ),
            "arguments": self._arguments(
                node.args
            ),
            "decorators": [
                self._node_name(
                    decorator
                )
                for decorator in node.decorator_list
            ],
            "docstring": (
                ast.get_docstring(node)
                or ""
            ),
            "is_async": is_async
        }

        if class_stack:
            result["methods"].append(
                item
            )

        elif is_async:
            result[
                "async_functions"
            ].append(
                item
            )

        else:
            result[
                "functions"
            ].append(
                item
            )

        for child in node.body:
            if isinstance(
                child,
                (
                    ast.FunctionDef,
                    ast.AsyncFunctionDef,
                    ast.ClassDef
                )
            ):
                self._collect_node(
                    node=child,
                    result=result,
                    class_stack=class_stack
                )

    def _arguments(
        self,
        arguments: ast.arguments
    ) -> list[str]:

        names = []

        for argument in arguments.posonlyargs:
            names.append(
                argument.arg
            )

        for argument in arguments.args:
            names.append(
                argument.arg
            )

        if arguments.vararg is not None:
            names.append(
                f"*{arguments.vararg.arg}"
            )

        for argument in arguments.kwonlyargs:
            names.append(
                argument.arg
            )

        if arguments.kwarg is not None:
            names.append(
                f"**{arguments.kwarg.arg}"
            )

        return names

    def _node_name(
        self,
        node: ast.AST
    ) -> str:

        if isinstance(
            node,
            ast.Name
        ):
            return node.id

        if isinstance(
            node,
            ast.Attribute
        ):
            parent = self._node_name(
                node.value
            )

            if parent:
                return (
                    f"{parent}.{node.attr}"
                )

            return node.attr

        if isinstance(
            node,
            ast.Subscript
        ):
            return self._node_name(
                node.value
            )

        if isinstance(
            node,
            ast.Call
        ):
            return self._node_name(
                node.func
            )

        try:
            return ast.unparse(
                node
            )

        except Exception:
            return ""