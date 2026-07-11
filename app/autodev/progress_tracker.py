from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class ProgressEvent:
    step_id: str
    status: str
    timestamp: str
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ProgressTracker:
    """
    Śledzi postęp pojedynczej sesji AutoDev.
    """

    def __init__(self) -> None:
        self.session_id: str = ""
        self.total_steps: int = 0
        self.current_step: str = ""
        self.events: list[ProgressEvent] = []
        self.started_at: str = ""
        self.finished_at: str = ""

    def start(
        self,
        *,
        session_id: str,
        total_steps: int,
    ) -> dict[str, Any]:

        self.session_id = str(
            session_id
        ).strip()

        self.total_steps = max(
            0,
            int(total_steps),
        )

        self.current_step = ""
        self.events = []
        self.started_at = datetime.now().isoformat()
        self.finished_at = ""

        return self.status()

    def update(
        self,
        *,
        step_id: str,
        status: str,
        message: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, Any]:

        self.current_step = str(
            step_id
        )

        event = ProgressEvent(
            step_id=str(step_id),
            status=str(status).upper(),
            timestamp=datetime.now().isoformat(),
            message=str(message),
            metadata=dict(metadata or {}),
        )

        self.events.append(
            event
        )

        if event.status in {
            "COMPLETED",
            "FAILED",
            "ROLLED_BACK",
            "CANCELLED",
        } and self._is_terminal_session_event(event):
            self.finished_at = event.timestamp

        return self.status()

    def percentage(
        self,
    ) -> float:

        if self.total_steps <= 0:
            return 0.0

        completed_steps = {
            event.step_id
            for event in self.events
            if event.status == "COMPLETED"
        }

        return round(
            min(
                len(completed_steps)
                / self.total_steps
                * 100.0,
                100.0,
            ),
            2,
        )

    def _is_terminal_session_event(
        self,
        event: ProgressEvent,
    ) -> bool:

        return event.step_id in {
            "session",
            "workflow",
            "final",
        }

    def status(
        self,
    ) -> dict[str, Any]:

        return {
            "session_id": self.session_id,
            "total_steps": self.total_steps,
            "current_step": self.current_step,
            "percentage": self.percentage(),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "events": [
                event.to_dict()
                for event in self.events
            ],
        }
