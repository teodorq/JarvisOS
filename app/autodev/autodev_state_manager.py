from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class AutoDevState:
    status: str = "IDLE"
    cycle_id: str = ""
    goal: str = ""
    current_step: str = ""
    started_at: str = ""
    updated_at: str = ""
    finished_at: str = ""
    last_error: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class AutoDevStateManager:
    def __init__(self) -> None:
        self.state = AutoDevState()

    def start(
        self,
        *,
        cycle_id: str,
        goal: str,
    ) -> dict[str, Any]:
        now = datetime.now().isoformat()
        self.state = AutoDevState(
            status="RUNNING",
            cycle_id=str(cycle_id),
            goal=str(goal),
            current_step="START",
            started_at=now,
            updated_at=now,
        )
        return self.status()

    def update(
        self,
        *,
        step: str,
        status: str = "RUNNING",
    ) -> dict[str, Any]:
        self.state.current_step = str(step)
        self.state.status = str(status).upper()
        self.state.updated_at = datetime.now().isoformat()
        return self.status()

    def finish(
        self,
        *,
        status: str,
        error: str = "",
    ) -> dict[str, Any]:
        now = datetime.now().isoformat()
        self.state.status = str(status).upper()
        self.state.updated_at = now
        self.state.finished_at = now
        self.state.last_error = str(error)
        return self.status()

    def reset(self) -> dict[str, Any]:
        self.state = AutoDevState()
        return self.status()

    def status(self) -> dict[str, Any]:
        return self.state.to_dict()
