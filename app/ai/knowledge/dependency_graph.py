from __future__ import annotations

from pathlib import Path


class DependencyGraphBuilder:
    def build(
        self,
        project_root: str | Path,
        code_map: dict[str, dict],
    ) -> dict[str, list[str]]:
        root = Path(project_root).resolve()
        known_modules = self._known_modules(code_map)
        graph: dict[str, list[str]] = {}

        for relative, data in code_map.items():
            module = self._path_to_module(relative)
            dependencies: list[str] = []
            for imported in data.get("imports", []):
                match = self._match_project_module(imported, known_modules)
                if match and match != module:
                    dependencies.append(match)
            graph[module] = sorted(set(dependencies))

        return graph

    @staticmethod
    def _known_modules(code_map: dict[str, dict]) -> set[str]:
        return {DependencyGraphBuilder._path_to_module(path) for path in code_map}

    @staticmethod
    def _path_to_module(path: str) -> str:
        module = path[:-3] if path.endswith(".py") else path
        module = module.replace("/", ".").replace("\\", ".")
        if module.endswith(".__init__"):
            module = module[: -len(".__init__")]
        return module

    @staticmethod
    def _match_project_module(imported: str, known_modules: set[str]) -> str | None:
        if imported in known_modules:
            return imported
        candidates = [module for module in known_modules if module.startswith(imported + ".")]
        if candidates:
            return min(candidates, key=len)
        parent_candidates = [module for module in known_modules if imported.startswith(module + ".")]
        if parent_candidates:
            return max(parent_candidates, key=len)
        return None
