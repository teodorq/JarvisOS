from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class LifecycleState:
    running: bool = False
    last_task_id: str = ""
    last_status: str = "IDLE"
    cycles_completed: int = 0
    recovery_count: int = 0
    updated_at: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class LifecycleStateStore:

    def __init__(
        self,
        path: str = "data/autodev/lifecycle_state.json",
    ) -> None:
        self.path = Path(path)

    def load(self) -> LifecycleState:
        if not self.path.exists():
            return LifecycleState()

        try:
            data = json.loads(
                self.path.read_text(encoding="utf-8")
            )
        except (OSError, json.JSONDecodeError):
            return LifecycleState()

        if not isinstance(data, dict):
            return LifecycleState()

        return LifecycleState(
            running=bool(data.get("running", False)),
            last_task_id=str(data.get("last_task_id", "")),
            last_status=str(data.get("last_status", "IDLE")),
            cycles_completed=int(data.get("cycles_completed", 0)),
            recovery_count=int(data.get("recovery_count", 0)),
            updated_at=str(data.get("updated_at", "")),
        )

    def save(
        self,
        state: LifecycleState,
    ) -> None:
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        state.updated_at = datetime.now().isoformat()

        temporary = self.path.with_suffix(
            self.path.suffix + ".tmp"
        )

        temporary.write_text(
            json.dumps(
                state.to_dict(),
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )

        temporary.replace(self.path)
