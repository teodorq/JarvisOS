from dataclasses import asdict, dataclass, field
from typing import Any

@dataclass(slots=True)
class TestPlan:
    changed_files: list[str] = field(default_factory=list)
    commands: list[list[str]] = field(default_factory=list)
    timeout_seconds: int = 180

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)
