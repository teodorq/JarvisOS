from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class NaturalActionRequest:
    original: str
    command: str
    intent: str
    confidence: float = 0.0
    slots: dict[str, Any] = field(default_factory=dict)
    missing: list[str] = field(default_factory=list)
    clarification: str = ""
    confirmation: str = ""
    used_context: bool = False
    read_only: bool = True

    @property
    def can_execute(self) -> bool:
        return self.intent != "standard"

    @property
    def complete(self) -> bool:
        return self.can_execute and not self.missing
