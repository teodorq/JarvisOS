import json
from pathlib import Path

from app.code.code_parser import CodeParser
from app.code.project_scanner import ProjectScanner


class SymbolIndex:

    def __init__(self):
        self.scanner = ProjectScanner()
        self.parser = CodeParser()
        self.index = None
        self.cache_file = Path("data/cache/symbol_index.json")
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)

    def build(self):
        classes = []
        functions = []
        imports = []

        for path in self.scanner.list_python_files():
            parsed = self.parser.parse_file(path)

            if parsed.get("error"):
                continue

            for cls in parsed.get("classes", []):
                classes.append({
                    "name": cls["name"],
                    "path": path,
                    "line": cls["line"],
                    "methods": cls.get("methods", [])
                })

            for func in parsed.get("functions", []):
                functions.append({
                    "name": func["name"],
                    "path": path,
                    "line": func["line"]
                })

            for imp in parsed.get("imports", []):
                imports.append({
                    **imp,
                    "path": path
                })

        self.index = {
            "classes": classes,
            "functions": functions,
            "imports": imports
        }

        self._save_cache()

        return self.index

    def get_index(self):
        if self.index is not None:
            return self.index

        cached = self._load_cache()

        if cached:
            self.index = cached
            return self.index

        return self.build()

    def rebuild(self):
        self.index = None
        return self.build()

    def find_class(self, name: str):
        name = name.lower().strip()
        results = []

        for item in self.get_index()["classes"]:
            if name in item["name"].lower():
                results.append(item)

        return results

    def find_function(self, name: str):
        name = name.lower().strip()
        results = []

        for item in self.get_index()["functions"]:
            if name in item["name"].lower():
                results.append(item)

        return results

    def summary(self):
        index = self.get_index()

        return (
            "SYMBOL INDEX\n"
            f"Klasy: {len(index['classes'])}\n"
            f"Funkcje: {len(index['functions'])}\n"
            f"Importy: {len(index['imports'])}\n"
            f"Cache: {self.cache_file}"
        )

    def _save_cache(self):
        if self.index is None:
            return

        with open(self.cache_file, "w", encoding="utf-8") as file:
            json.dump(
                self.index,
                file,
                indent=4,
                ensure_ascii=False
            )

    def _load_cache(self):
        if not self.cache_file.exists():
            return None

        try:
            with open(self.cache_file, "r", encoding="utf-8") as file:
                data = json.load(file)

            if not isinstance(data, dict):
                return None

            if "classes" not in data:
                return None

            if "functions" not in data:
                return None

            if "imports" not in data:
                return None

            return data

        except Exception:
            return None