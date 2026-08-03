from app.core.project_paths import (
    default_project_path,
    default_project_root,
)

from pathlib import Path

from app.autodev.import_analyzer import ImportAnalyzer
from app.autodev.reference_finder import ReferenceFinder
from app.code.project_scanner import ProjectScanner


class DependencyGraph:

    def __init__(self, root_path=default_project_root()):
        self.root_path = Path(root_path)
        self.scanner = ProjectScanner(root_path)
        self.import_analyzer = ImportAnalyzer()
        self.reference_finder = ReferenceFinder()

        self.files = {}
        self.import_edges = []
        self.reference_edges = []

    def build(self):
        self.files = {}
        self.import_edges = []
        self.reference_edges = []

        python_files = self.scanner.list_python_files()

        module_map = self._build_module_map(python_files)

        for path in python_files:
            self.files[path] = {
                "path": path,
                "imports": [],
                "references": []
            }

            import_result = self.import_analyzer.analyze_file(path)

            for item in import_result.get("imports", []):
                module = item.get("module", "")
                target_path = self._resolve_module(module, module_map)

                edge = {
                    "source": path,
                    "target": target_path,
                    "module": module,
                    "name": item.get("name", ""),
                    "line": item.get("line", 0)
                }

                self.files[path]["imports"].append(edge)
                self.import_edges.append(edge)

        return self.summary()

    def find_symbol_references(self, symbol_name: str):
        references = []

        for path in self.scanner.list_python_files():
            file_references = self.reference_finder.find_references(
                path,
                symbol_name
            )

            references.extend(file_references)

        self.reference_edges = references
        return references

    def files_using_module(self, module_name: str):
        results = []
        module_name = module_name.lower().strip()

        for edge in self.import_edges:
            module = edge.get("module", "").lower()

            if module_name in module:
                results.append(edge)

        return results

    def impact_for_symbol(self, symbol_name: str):
        references = self.find_symbol_references(symbol_name)

        files = sorted({
            item.get("path", "")
            for item in references
            if item.get("path")
        })

        return {
            "symbol": symbol_name,
            "references_count": len(references),
            "files_count": len(files),
            "files": files,
            "references": references
        }

    def summary(self):
        return {
            "files": len(self.files),
            "import_edges": len(self.import_edges),
            "reference_edges": len(self.reference_edges)
        }

    def summary_text(self):
        summary = self.summary()

        return (
            "DEPENDENCY GRAPH\n"
            f"Pliki: {summary['files']}\n"
            f"Importy: {summary['import_edges']}\n"
            f"Referencje: {summary['reference_edges']}"
        )

    def _build_module_map(self, python_files):
        module_map = {}

        for path in python_files:
            file_path = Path(path)

            try:
                relative = file_path.relative_to(self.root_path)
            except ValueError:
                continue

            module_name = ".".join(relative.with_suffix("").parts)
            module_map[module_name] = str(file_path)

        return module_map

    def _resolve_module(self, module_name: str, module_map: dict):
        if module_name in module_map:
            return module_map[module_name]

        for known_module, path in module_map.items():
            if known_module.endswith(module_name):
                return path

        return ""