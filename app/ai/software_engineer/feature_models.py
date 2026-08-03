from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass
class FeatureFileSpec:
    file_id: str
    relative_path: str
    purpose: str
    category: str
    dependencies: list[str] = field(default_factory=list)
    required: bool = True
    integration_points: list[str] = field(default_factory=list)
    acceptance_criteria: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class FeatureBlueprint:
    feature_name: str
    feature_slug: str
    objective: str
    package_path: str
    files: list[FeatureFileSpec]
    creation_order: list[str]
    validation_targets: list[str]
    rollback_scope: list[str]
    estimated_roi: float
    estimated_risk: float
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "feature_name": self.feature_name,
            "feature_slug": self.feature_slug,
            "objective": self.objective,
            "package_path": self.package_path,
            "files": [
                item.to_dict()
                for item in self.files
            ],
            "creation_order": list(
                self.creation_order
            ),
            "validation_targets": list(
                self.validation_targets
            ),
            "rollback_scope": list(
                self.rollback_scope
            ),
            "estimated_roi": self.estimated_roi,
            "estimated_risk": self.estimated_risk,
            "metadata": dict(
                self.metadata
            ),
        }

    def file_map(
        self,
    ) -> dict[str, FeatureFileSpec]:
        return {
            item.file_id: item
            for item in self.files
        }
