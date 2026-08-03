from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(slots=True)
class CodeIssue:
    category: str
    path: str
    message: str
    severity: str = "medium"
    line: int | None = None
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class KnowledgeTask:
    title: str
    description: str
    priority: int
    source: str = "autonomous_knowledge_engine"
    risk: float = 0.5
    roi: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class KnowledgeReport:
    project_root: str
    scanned_files: int
    python_files: int
    issues: list[CodeIssue] = field(default_factory=list)
    tasks: list[KnowledgeTask] = field(default_factory=list)
    dependency_graph: dict[str, list[str]] = field(default_factory=dict)
    code_map: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def issue_count(self) -> int:
        return len(self.issues)

    def to_dict(self) -> dict[str, Any]:
        return {
            "project_root": self.project_root,
            "scanned_files": self.scanned_files,
            "python_files": self.python_files,
            "issue_count": self.issue_count,
            "issues": [item.to_dict() for item in self.issues],
            "tasks": [item.to_dict() for item in self.tasks],
            "dependency_graph": self.dependency_graph,
            "code_map": self.code_map,
        }
