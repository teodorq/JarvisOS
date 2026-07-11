import ast
from pathlib import Path


class ImportAnalyzer:

    def analyze_file(self, path: str) -> dict:
        file_path = Path(path)

        result = {
            "path": str(file_path),
            "imports": [],
            "error": None
        }

        if not file_path.exists():
            result["error"] = "Plik nie istnieje."
            return result

        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source)

        except Exception as error:
            result["error"] = str(error)
            return result

        for node in ast.walk(tree):

            if isinstance(node, ast.Import):
                for alias in node.names:
                    result["imports"].append({
                        "type": "import",
                        "module": alias.name,
                        "name": alias.name,
                        "alias": alias.asname or "",
                        "line": node.lineno
                    })

            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""

                for alias in node.names:
                    result["imports"].append({
                        "type": "from",
                        "module": module,
                        "name": alias.name,
                        "alias": alias.asname or "",
                        "line": node.lineno
                    })

        return result