import ast
from pathlib import Path


class CodeExtractor:

    def extract_class(self, path: str, class_name: str):
        return self._extract_node(
            path=path,
            node_name=class_name,
            node_type=ast.ClassDef
        )

    def extract_function(self, path: str, function_name: str):
        return self._extract_node(
            path=path,
            node_name=function_name,
            node_type=ast.FunctionDef
        )

    def _extract_node(self, path: str, node_name: str, node_type):
        file_path = Path(path)

        if not file_path.exists():
            return f"Plik nie istnieje: {path}"

        try:
            source = file_path.read_text(encoding="utf-8")
            lines = source.splitlines()
            tree = ast.parse(source)

            for node in ast.walk(tree):
                if isinstance(node, node_type) and node.name == node_name:
                    start = node.lineno
                    end = getattr(node, "end_lineno", None)

                    if end is None:
                        return "Nie udało się ustalić końca fragmentu."

                    fragment = lines[start - 1:end]

                    return "\n".join(fragment)

            return f"Nie znaleziono: {node_name}"

        except Exception as error:
            return f"Błąd odczytu kodu: {error}"