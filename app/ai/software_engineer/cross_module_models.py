from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from .refactor_models import MultiFileRefactorPlan


@dataclass(frozen=True, slots=True)
class CrossModuleDependency:
    source_module: str
    target_module: str
    source_path: str
    target_path: str

    def to_dict(self) -> dict[str, str]:
        return {
            "source_module": self.source_module,
            "target_module": self.target_module,
            "source_path": self.source_path,
            "target_path": self.target_path,
        }


@dataclass(slots=True)
class CrossModuleChangePlan:
    objective: str
    refactor_plan: MultiFileRefactorPlan
    subsystems: dict[str, list[str]]
    module_order: list[str]
    file_order: list[str]
    dependency_edges: list[CrossModuleDependency]
    validation_batches: list[list[str]]
    estimated_risk: float
    risk_level: str
    estimated_roi: float
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def blocked(self) -> bool:
        return bool(self.blockers)

    @property
    def files(self):
        return self.refactor_plan.files

    @property
    def impacted_files(self) -> list[str]:
        return list(self.refactor_plan.impacted_files)

    @property
    def rollback_scope(self) -> list[str]:
        return list(self.refactor_plan.rollback_scope)

    def replacements(self) -> dict[str, str]:
        return self.refactor_plan.replacements()

    def to_dict(self) -> dict[str, Any]:
        return {
            "objective": self.objective,
            "subsystems": {
                key: list(value)
                for key, value in self.subsystems.items()
            },
            "subsystem_count": len(self.subsystems),
            "module_order": list(self.module_order),
            "file_order": list(self.file_order),
            "dependency_edges": [
                edge.to_dict()
                for edge in self.dependency_edges
            ],
            "validation_batches": [
                list(batch)
                for batch in self.validation_batches
            ],
            "estimated_risk": self.estimated_risk,
            "risk_level": self.risk_level,
            "estimated_roi": self.estimated_roi,
            "blocked": self.blocked,
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "impacted_files": self.impacted_files,
            "rollback_scope": self.rollback_scope,
            "refactor_plan": self.refactor_plan.to_dict(),
            "metadata": dict(self.metadata),
        }
