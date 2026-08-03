from __future__ import annotations

import ast
from pathlib import Path
from typing import Iterable

from app.autodev.execution_policy import (
    ExecutionPolicy,
    ProjectBoundaryPolicy,
)

from .refactor_models import (
    MultiFileRefactorPlan,
    RefactorFilePlan,
)
from .refactor_source_index import (
    RefactorSourceIndex,
)


class MultiFileRefactorAnalyzer:
    """Builds a bounded impact plan for existing Python files."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        max_files: int = 12,
        max_impact_files: int = 200,
        source_index: RefactorSourceIndex | None = None,
    ) -> None:
        self.project_root = Path(
            project_root
        ).expanduser().resolve(
            strict=False
        )
        self.max_files = max(
            2,
            int(max_files),
        )
        self.max_impact_files = max(
            self.max_files,
            int(max_impact_files),
        )
        self.boundary = ProjectBoundaryPolicy(
            ExecutionPolicy(
                project_root=self.project_root,
                allowed_extensions=(
                    ".py",
                ),
            )
        )
        self.source_index = (
            source_index
            or RefactorSourceIndex(
                self.project_root
            )
        )

    def analyze(
        self,
        objective: str,
        replacements: dict[str, str],
        *,
        allow_public_symbol_removal: bool = False,
    ) -> MultiFileRefactorPlan:
        objective = " ".join(
            str(objective).split()
        ).strip()

        if not objective:
            raise ValueError(
                "Cel refaktoryzacji nie może być pusty."
            )

        normalized = self._normalize_replacements(
            replacements
        )
        project_files = (
            self.source_index
            .project_python_files()
        )
        modules = {
            path: self.source_index.module_name(
                path
            )
            for path in normalized
        }
        absolute_replacements = {
            str(
                self.project_root
                / path
            ): content
            for path, content in normalized.items()
        }
        graph_before = (
            self.source_index
            .module_graph(
                project_files
            )
        )
        graph_after = (
            self.source_index
            .module_graph(
                project_files,
                replacements=absolute_replacements,
            )
        )
        cycles_before = (
            self.source_index.cycles(
                graph_before
            )
        )
        cycles_after = (
            self.source_index.cycles(
                graph_after
            )
        )
        modified_modules = set(
            modules.values()
        )
        new_cycles = [
            sorted(cycle)
            for cycle in sorted(
                cycles_after - cycles_before,
                key=lambda item: tuple(
                    sorted(item)
                ),
            )
            if cycle & modified_modules
        ]
        file_plans = [
            self._file_plan(
                path,
                content,
                modules[path],
            )
            for path, content in normalized.items()
        ]
        module_to_relative = {
            self.source_index.module_name(
                self.source_index.relative_path(
                    path
                )
            ): self.source_index.relative_path(
                path
            )
            for path in project_files
        }
        reverse_dependents = (
            self.source_index
            .reverse_dependents(
                graph_after,
                module_to_relative,
            )
        )
        target_paths = set(
            normalized
        )
        impacted = set(
            target_paths
        )
        blockers: list[str] = []
        warnings: list[str] = []

        for plan in file_plans:
            dependents = sorted(
                reverse_dependents.get(
                    plan.module_name,
                    set(),
                )
                - target_paths
            )
            references = (
                self.source_index
                .reference_files(
                    project_files,
                    symbols=plan.changed_symbols,
                    excluded=target_paths,
                )
            )
            plan.direct_dependents = (
                dependents
            )
            plan.reference_files = (
                references
            )
            impacted.update(
                dependents
            )
            impacted.update(
                references
            )
            blockers.extend(
                self._public_removal_blockers(
                    plan,
                    project_files,
                    target_paths,
                    allow_public_symbol_removal,
                )
            )

            if plan.signature_changes:
                warning = (
                    "Zmiana sygnatur w "
                    f"{plan.relative_path}: "
                    + ", ".join(
                        plan.signature_changes
                    )
                )
                warnings.append(
                    warning
                )
                plan.risk_reasons.append(
                    warning
                )

            if dependents:
                plan.risk_reasons.append(
                    "Bezpośredni dependenci: "
                    f"{len(dependents)}"
                )

            if references:
                plan.risk_reasons.append(
                    "Pliki z referencjami: "
                    f"{len(references)}"
                )

        if new_cycles:
            blockers.append(
                "Refaktoryzacja tworzy nowe cykle importów: "
                + "; ".join(
                    " -> ".join(cycle)
                    for cycle in new_cycles
                )
            )

        impacted_files = sorted(
            impacted
        )

        if len(
            impacted_files
        ) > self.max_impact_files:
            blockers.append(
                "Zakres wpływu przekracza limit "
                f"{self.max_impact_files} plików."
            )

        baseline_hashes = {
            path: self.source_index.hash_path(
                self.project_root
                / path
            )
            for path in impacted_files
            if (
                self.project_root
                / path
            ).is_file()
        }
        risk = self._risk_score(
            file_plans,
            impacted_files,
            new_cycles,
        )

        return MultiFileRefactorPlan(
            objective=objective,
            files=file_plans,
            impacted_files=impacted_files,
            validation_targets=impacted_files,
            rollback_scope=sorted(
                target_paths
            ),
            baseline_hashes=baseline_hashes,
            estimated_risk=risk,
            risk_level=self._risk_level(
                risk
            ),
            estimated_roi=self._roi_score(
                file_plans
            ),
            blockers=self._unique(
                blockers
            ),
            warnings=self._unique(
                warnings
            ),
            new_import_cycles=new_cycles,
            metadata={
                "source": (
                    "multi_file_refactor_analyzer"
                ),
                "operation": "refactor",
                "multi_file": True,
                "allow_create": False,
                "allow_public_symbol_removal": bool(
                    allow_public_symbol_removal
                ),
                "changed_symbols": {
                    item.relative_path: list(
                        item.changed_symbols
                    )
                    for item in file_plans
                },
            },
        )

    def _normalize_replacements(
        self,
        replacements: dict[str, str],
    ) -> dict[str, str]:
        if not isinstance(
            replacements,
            dict,
        ):
            raise TypeError(
                "replacements musi być słownikiem."
            )

        if (
            len(replacements) < 2
            or len(replacements) > self.max_files
        ):
            raise ValueError(
                "Refaktoryzacja wieloplikowa wymaga od 2 do "
                f"{self.max_files} plików."
            )

        normalized: dict[str, str] = {}

        for raw_path, raw_content in replacements.items():
            target = self.boundary.resolve_target(
                raw_path,
                require_file=True,
                allow_missing=False,
            )
            relative = (
                self.source_index
                .relative_path(
                    target
                )
            )
            content = str(
                raw_content
            )

            if not content.strip():
                raise ValueError(
                    "Nowa zawartość nie może być pusta: "
                    f"{relative}"
                )

            if not content.endswith(
                "\n"
            ):
                content += "\n"

            ast.parse(
                content,
                filename=str(target),
            )
            old_content = target.read_text(
                encoding="utf-8"
            )

            if old_content == content:
                raise ValueError(
                    "Brak rzeczywistej zmiany w pliku: "
                    f"{relative}"
                )

            if relative in normalized:
                raise ValueError(
                    "Duplikat ścieżki refaktoryzacji: "
                    f"{relative}"
                )

            normalized[
                relative
            ] = content

        return dict(
            sorted(
                normalized.items()
            )
        )

    def _file_plan(
        self,
        relative: str,
        new_content: str,
        module_name: str,
    ) -> RefactorFilePlan:
        target = self.project_root / relative
        old_content = target.read_text(
            encoding="utf-8"
        )
        old_tree = ast.parse(
            old_content,
            filename=str(target),
        )
        new_tree = ast.parse(
            new_content,
            filename=str(target),
        )
        old_symbols = self.source_index.symbols(
            old_tree
        )
        new_symbols = self.source_index.symbols(
            new_tree
        )
        changed = sorted(
            name
            for name in (
                set(old_symbols)
                | set(new_symbols)
            )
            if old_symbols.get(
                name,
                {},
            ).get(
                "fingerprint"
            )
            != new_symbols.get(
                name,
                {},
            ).get(
                "fingerprint"
            )
        )
        removed_public = sorted(
            name
            for name in (
                set(old_symbols)
                - set(new_symbols)
            )
            if not name.startswith(
                "_"
            )
        )
        signature_changes = sorted(
            name
            for name in (
                set(old_symbols)
                & set(new_symbols)
            )
            if old_symbols[name].get(
                "signature"
            )
            != new_symbols[name].get(
                "signature"
            )
        )

        return RefactorFilePlan(
            relative_path=relative,
            module_name=module_name,
            old_sha256=(
                self.source_index.hash_text(
                    old_content
                )
            ),
            new_sha256=(
                self.source_index.hash_text(
                    new_content
                )
            ),
            old_lines=len(
                old_content.splitlines()
            ),
            new_lines=len(
                new_content.splitlines()
            ),
            changed_symbols=changed,
            removed_public_symbols=removed_public,
            signature_changes=signature_changes,
            imports_before=(
                self.source_index.imports(
                    old_tree,
                    source_module=module_name,
                    source_path=relative,
                )
            ),
            imports_after=(
                self.source_index.imports(
                    new_tree,
                    source_module=module_name,
                    source_path=relative,
                )
            ),
            old_content=old_content,
            new_content=new_content,
        )

    def _public_removal_blockers(
        self,
        plan: RefactorFilePlan,
        project_files: list[Path],
        target_paths: set[str],
        allowed: bool,
    ) -> list[str]:
        if (
            allowed
            or not plan.removed_public_symbols
        ):
            return []

        references = (
            self.source_index
            .reference_files(
                project_files,
                symbols=(
                    plan.removed_public_symbols
                ),
                excluded=target_paths,
            )
        )

        if not references:
            return []

        return [
            (
                "Usunięcie publicznych symboli "
                f"{', '.join(plan.removed_public_symbols)} "
                f"z {plan.relative_path} ma referencje w: "
                + ", ".join(
                    references
                )
            )
        ]

    @staticmethod
    def _risk_score(
        files: list[RefactorFilePlan],
        impacted_files: list[str],
        new_cycles: list[list[str]],
    ) -> float:
        removed = sum(
            len(item.removed_public_symbols)
            for item in files
        )
        signatures = sum(
            len(item.signature_changes)
            for item in files
        )

        return min(
            100.0,
            round(
                8.0
                + len(files) * 4.0
                + max(
                    0,
                    len(impacted_files)
                    - len(files),
                )
                * 0.75
                + signatures * 7.0
                + removed * 18.0
                + len(new_cycles) * 25.0,
                2,
            ),
        )

    @staticmethod
    def _roi_score(
        files: list[RefactorFilePlan],
    ) -> float:
        changed_symbols = {
            symbol
            for item in files
            for symbol in item.changed_symbols
        }

        return round(
            min(
                98.0,
                60.0
                + len(files) * 5.0
                + len(changed_symbols) * 1.5,
            ),
            2,
        )

    @staticmethod
    def _risk_level(
        score: float,
    ) -> str:
        if score <= 20.0:
            return "LOW"

        if score <= 45.0:
            return "MEDIUM"

        if score <= 65.0:
            return "HIGH"

        return "CRITICAL"

    @staticmethod
    def _unique(
        values: Iterable[str],
    ) -> list[str]:
        result: list[str] = []

        for value in values:
            text = str(
                value
            ).strip()

            if text and text not in result:
                result.append(
                    text
                )

        return result
