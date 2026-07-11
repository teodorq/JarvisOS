import ast
from pathlib import Path


class ReferenceFinder:

    def find_references(self, path: str, symbol_name: str) -> list:
        file_path = Path(path)

        if not file_path.exists():
            return []

        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source)

        except Exception:
            return []

        references = []

        for node in ast.walk(tree):

            if isinstance(node, ast.Name) and node.id == symbol_name:
                references.append({
                    "path": str(file_path),
                    "symbol": symbol_name,
                    "line": node.lineno,
                    "column": node.col_offset,
                    "kind": "name"
                })

            elif isinstance(node, ast.Attribute) and node.attr == symbol_name:
                references.append({
                    "path": str(file_path),
                    "symbol": symbol_name,
                    "line": node.lineno,
                    "column": node.col_offset,
                    "kind": "attribute"
                })

            elif isinstance(node, ast.Call):
                function_name = self._call_name(node.func)

                if function_name == symbol_name:
                    references.append({
                        "path": str(file_path),
                        "symbol": symbol_name,
                        "line": node.lineno,
                        "column": node.col_offset,
                        "kind": "call"
                    })

        return references

    def _call_name(self, node):
        if isinstance(node, ast.Name):
            return node.id

        if isinstance(node, ast.Attribute):
            return node.attr

        return ""