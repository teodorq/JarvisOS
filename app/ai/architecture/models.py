from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class ArchitectureIssue:
    code: str
    message: str
    severity: str
    file_path: str = ""
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class ArchitectureReport:
    files_scanned: int
    modules_scanned: int
    dependency_count: int
    circular_dependencies: list[list[str]]
    high_coupling_modules: dict[str, int]
    large_files: dict[str, int]
    large_classes: dict[str, int]
    issues: list[ArchitectureIssue]
    architecture_score: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "files_scanned": self.files_scanned,
            "modules_scanned": self.modules_scanned,
            "dependency_count": self.dependency_count,
            "circular_dependencies": self.circular_dependencies,
            "high_coupling_modules": self.high_coupling_modules,
            "large_files": self.large_files,
            "large_classes": self.large_classes,
            "issues": [
                {
                    "code": issue.code,
                    "message": issue.message,
                    "severity": issue.severity,
                    "file_path": issue.file_path,
                    "details": dict(issue.details),
                }
                for issue in self.issues
            ],
            "architecture_score": self.architecture_score,
        }
