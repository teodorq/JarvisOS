from __future__ import annotations

from pathlib import PurePosixPath, Path
from typing import Iterable

from .cross_module_models import (
    CrossModuleChangePlan,
    CrossModuleDependency,
)
from .multi_file_refactor_analyzer import (
    MultiFileRefactorAnalyzer,
)


class CrossModuleChangePlanner:
    """Builds an ordered, bounded plan spanning project subsystems."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        analyzer: MultiFileRefactorAnalyzer | None = None,
        max_subsystems: int = 6,
    ) -> None:
        self.project_root = Path(project_root).expanduser().resolve(
            strict=False
        )
        self.analyzer = (
            analyzer
            or MultiFileRefactorAnalyzer(self.project_root)
        )
        self.max_subsystems = max(2, int(max_subsystems))

    def plan(
        self,
        objective: str,
        replacements: dict[str, str],
        *,
        allow_public_symbol_removal: bool = False,
        allow_same_subsystem: bool = False,
        required_subsystems: Iterable[str] = (),
    ) -> CrossModuleChangePlan:
        refactor_plan = self.analyzer.analyze(
            objective,
            replacements,
            allow_public_symbol_removal=(
                allow_public_symbol_removal
            ),
        )
        subsystems = self._subsystems(refactor_plan)
        required = self._required(required_subsystems)
        blockers = list(refactor_plan.blockers)
        warnings = list(refactor_plan.warnings)

        if len(subsystems) < 2 and not allow_same_subsystem:
            blockers.append(
                "Zmiana między modułami wymaga plików z co "
                "najmniej dwóch podsystemów projektu."
            )

        if len(subsystems) > self.max_subsystems:
            blockers.append(
                "Zakres zmiany przekracza limit "
                f"{self.max_subsystems} podsystemów."
            )

        missing = sorted(
            set(required) - set(subsystems)
        )

        if missing:
            blockers.append(
                "Brakuje wymaganych podsystemów: "
                + ", ".join(missing)
            )

        edges = self._dependency_edges(refactor_plan)
        cross_edges = [
            edge
            for edge in edges
            if self._subsystem(edge.source_path)
            != self._subsystem(edge.target_path)
        ]

        if not cross_edges and len(subsystems) >= 2:
            warnings.append(
                "Zmiana obejmuje wiele podsystemów, ale nie "
                "wykryto bezpośredniej zależności importowej "
                "między modyfikowanymi plikami."
            )

        module_order, cyclic_modules = self._module_order(
            refactor_plan,
            edges,
        )

        if cyclic_modules:
            blockers.append(
                "Nie można ustalić bezpiecznej kolejności "
                "modułów z powodu cyklu: "
                + ", ".join(cyclic_modules)
            )

        module_to_path = {
            item.module_name: item.relative_path
            for item in refactor_plan.files
        }
        file_order = [
            module_to_path[module]
            for module in module_order
            if module in module_to_path
        ]
        validation_batches = self._validation_batches(
            file_order,
            refactor_plan.validation_targets,
        )
        risk = min(
            100.0,
            round(
                refactor_plan.estimated_risk
                + max(0, len(subsystems) - 1) * 5.0
                + len(cross_edges) * 2.0,
                2,
            ),
        )
        roi = min(
            100.0,
            round(
                refactor_plan.estimated_roi
                + len(cross_edges) * 2.5,
                2,
            ),
        )

        return CrossModuleChangePlan(
            objective=refactor_plan.objective,
            refactor_plan=refactor_plan,
            subsystems=subsystems,
            module_order=module_order,
            file_order=file_order,
            dependency_edges=edges,
            validation_batches=validation_batches,
            estimated_risk=risk,
            risk_level=self._risk_level(risk),
            estimated_roi=roi,
            blockers=self._unique(blockers),
            warnings=self._unique(warnings),
            metadata={
                "source": "cross_module_change_planner",
                "operation": "cross_module_change",
                "cross_module": True,
                "required_subsystems": required,
                "cross_subsystem_edges": len(cross_edges),
                "base_risk": refactor_plan.estimated_risk,
            },
        )

    def _subsystems(
        self,
        plan,
    ) -> dict[str, list[str]]:
        values: dict[str, list[str]] = {}

        for item in plan.files:
            group = self._subsystem(item.relative_path)
            values.setdefault(group, []).append(
                item.relative_path
            )

        return {
            key: sorted(paths)
            for key, paths in sorted(values.items())
        }

    @staticmethod
    def _subsystem(relative_path: str) -> str:
        parts = PurePosixPath(
            str(relative_path).replace("\\", "/")
        ).parts

        if not parts:
            return "unknown"

        if parts[0] == "app" and len(parts) >= 2:
            return ".".join(parts[:2])

        if parts[0] == "tests":
            return "tests"

        return parts[0]

    @staticmethod
    def _required(values: Iterable[str]) -> list[str]:
        if isinstance(values, (str, bytes)):
            values = [values]

        return sorted(
            {
                str(value).strip()
                for value in values
                if str(value).strip()
            }
        )

    @staticmethod
    def _dependency_edges(
        plan,
    ) -> list[CrossModuleDependency]:
        module_to_path = {
            item.module_name: item.relative_path
            for item in plan.files
        }
        edges: list[CrossModuleDependency] = []

        for item in plan.files:
            for imported in item.imports_after:
                target = CrossModuleChangePlanner._changed_module(
                    imported,
                    module_to_path,
                )

                if (
                    not target
                    or target == item.module_name
                ):
                    continue

                edge = CrossModuleDependency(
                    source_module=item.module_name,
                    target_module=target,
                    source_path=item.relative_path,
                    target_path=module_to_path[target],
                )

                if edge not in edges:
                    edges.append(edge)

        return sorted(
            edges,
            key=lambda edge: (
                edge.source_module,
                edge.target_module,
            ),
        )

    @staticmethod
    def _changed_module(
        imported: str,
        module_to_path: dict[str, str],
    ) -> str:
        imported = str(imported).strip()

        if imported in module_to_path:
            return imported

        matches = [
            module
            for module in module_to_path
            if (
                imported.startswith(module + ".")
                or module.startswith(imported + ".")
            )
        ]

        return max(matches, key=len) if matches else ""

    @staticmethod
    def _module_order(
        plan,
        edges: list[CrossModuleDependency],
    ) -> tuple[list[str], list[str]]:
        modules = {
            item.module_name
            for item in plan.files
        }
        dependencies = {
            module: set()
            for module in modules
        }

        for edge in edges:
            dependencies[edge.source_module].add(
                edge.target_module
            )

        order: list[str] = []
        pending = {
            module: set(values)
            for module, values in dependencies.items()
        }

        while pending:
            ready = sorted(
                module
                for module, values in pending.items()
                if not values
            )

            if not ready:
                return order + sorted(pending), sorted(pending)

            for module in ready:
                order.append(module)
                pending.pop(module, None)

            ready_set = set(ready)

            for values in pending.values():
                values.difference_update(ready_set)

        return order, []

    @staticmethod
    def _validation_batches(
        file_order: list[str],
        validation_targets: list[str],
    ) -> list[list[str]]:
        changed = list(file_order)
        changed_set = set(changed)
        impacted = sorted(
            path
            for path in validation_targets
            if path not in changed_set
            and not path.startswith("tests/")
        )
        tests = sorted(
            path
            for path in validation_targets
            if path.startswith("tests/")
        )
        batches = [
            batch
            for batch in (
                changed,
                impacted,
                tests,
            )
            if batch
        ]
        return batches

    @staticmethod
    def _risk_level(score: float) -> str:
        if score <= 25.0:
            return "LOW"
        if score <= 50.0:
            return "MEDIUM"
        if score <= 70.0:
            return "HIGH"
        return "CRITICAL"

    @staticmethod
    def _unique(values: Iterable[str]) -> list[str]:
        result: list[str] = []

        for value in values:
            text = str(value).strip()

            if text and text not in result:
                result.append(text)

        return result
