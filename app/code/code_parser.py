import ast
from pathlib import Path


class CodeParser:

    def parse_file(self, path: str):
        file_path = Path(path)

        if not file_path.exists():
            return {
                "path": str(file_path),
                "error": "Plik nie istnieje.",
                "classes": [],
                "functions": [],
                "imports": []
            }

        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source)

        except Exception as error:
            return {
                "path": str(file_path),
                "error": str(error),
                "classes": [],
                "functions": [],
                "imports": []
            }

        classes = []
        functions = []
        imports = []

        for node in ast.walk(tree):

            if isinstance(node, ast.ClassDef):
                classes.append({
                    "name": node.name,
                    "line": node.lineno,
                    "methods": self._class_methods(node)
                })

            if isinstance(node, ast.FunctionDef):
                functions.append({
                    "name": node.name,
                    "line": node.lineno
                })

            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append({
                        "type": "import",
                        "name": alias.name,
                        "line": node.lineno
                    })

            if isinstance(node, ast.ImportFrom):
                module = node.module or ""

                for alias in node.names:
                    imports.append({
                        "type": "from",
                        "module": module,
                        "name": alias.name,
                        "line": node.lineno
                    })

        return {
            "path": str(file_path),
            "error": None,
            "classes": classes,
            "functions": functions,
            "imports": imports
        }

    def _class_methods(self, class_node):
        methods = []

        for item in class_node.body:
            if isinstance(item, ast.FunctionDef):
                methods.append({
                    "name": item.name,
                    "line": item.lineno
                })

        return methods