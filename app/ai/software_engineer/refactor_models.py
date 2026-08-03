from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class RefactorFilePlan:
    relative_path: str
    module_name: str
    old_sha256: str
    new_sha256: str
    old_lines: int
    new_lines: int
    changed_symbols: list[str] = field(
        default_factory=list
    )
    removed_public_symbols: list[str] = field(
        default_factory=list
    )
    signature_changes: list[str] = field(
        default_factory=list
    )
    imports_before: list[str] = field(
        default_factory=list
    )
    imports_after: list[str] = field(
        default_factory=list
    )
    direct_dependents: list[str] = field(
        default_factory=list
    )
    reference_files: list[str] = field(
        default_factory=list
    )
    risk_reasons: list[str] = field(
        default_factory=list
    )
    metadata: dict[str, Any] = field(
        default_factory=dict
    )
    old_content: str = field(
        default="",
        repr=False,
    )
    new_content: str = field(
        default="",
        repr=False,
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "relative_path": self.relative_path,
            "module_name": self.module_name,
            "old_sha256": self.old_sha256,
            "new_sha256": self.new_sha256,
            "old_lines": self.old_lines,
            "new_lines": self.new_lines,
            "changed_symbols": list(
                self.changed_symbols
            ),
            "removed_public_symbols": list(
                self.removed_public_symbols
            ),
            "signature_changes": list(
                self.signature_changes
            ),
            "imports_before": list(
                self.imports_before
            ),
            "imports_after": list(
                self.imports_after
            ),
            "direct_dependents": list(
                self.direct_dependents
            ),
            "reference_files": list(
                self.reference_files
            ),
            "risk_reasons": list(
                self.risk_reasons
            ),
            "metadata": dict(
                self.metadata
            ),
        }


@dataclass(slots=True)
class MultiFileRefactorPlan:
    objective: str
    files: list[RefactorFilePlan]
    impacted_files: list[str]
    validation_targets: list[str]
    rollback_scope: list[str]
    baseline_hashes: dict[str, str]
    estimated_risk: float
    risk_level: str
    estimated_roi: float
    blockers: list[str] = field(
        default_factory=list
    )
    warnings: list[str] = field(
        default_factory=list
    )
    new_import_cycles: list[list[str]] = field(
        default_factory=list
    )
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    @property
    def blocked(self) -> bool:
        return bool(
            self.blockers
        )

    def replacements(
        self,
    ) -> dict[str, str]:
        return {
            item.relative_path: item.new_content
            for item in self.files
        }

    def file_map(
        self,
    ) -> dict[str, RefactorFilePlan]:
        return {
            item.relative_path: item
            for item in self.files
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "files": [
                item.to_dict()
                for item in self.files
            ],
            "impacted_files": list(
                self.impacted_files
            ),
            "validation_targets": list(
                self.validation_targets
            ),
            "rollback_scope": list(
                self.rollback_scope
            ),
            "baseline_hashes": dict(
                self.baseline_hashes
            ),
            "estimated_risk": self.estimated_risk,
            "risk_level": self.risk_level,
            "estimated_roi": self.estimated_roi,
            "blocked": self.blocked,
            "blockers": list(
                self.blockers
            ),
            "warnings": list(
                self.warnings
            ),
            "new_import_cycles": [
                list(cycle)
                for cycle in self.new_import_cycles
            ],
            "metadata": dict(
                self.metadata
            ),
        }
