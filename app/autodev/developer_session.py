from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Optional

from app.autodev.change_transaction import ChangeTransaction


@dataclass(slots=True)
class SessionEvent:
    event: str
    status: str
    timestamp: str
    note: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass
class DeveloperSession:
    goal: str = ""
    target: str = ""
    status: str = "idle"
    approved: bool = False

    transaction: Optional[ChangeTransaction] = None

    notes: list[str] = field(default_factory=list)
    history: list[SessionEvent] = field(default_factory=list)

    created_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )
    updated_at: str = field(
        default_factory=lambda: datetime.now().isoformat()
    )
    started_at: str | None = None
    finished_at: str | None = None

    def __post_init__(self) -> None:
        if not self.history:
            self._record_event("created")

    def start(
        self,
        goal: str,
        target: str = "",
    ) -> None:
        self.goal = str(goal).strip()
        self.target = str(target).strip()
        self.status = "planning"
        self.approved = False
        self.transaction = None
        self.notes = []
        self.history = []
        self.started_at = datetime.now().isoformat()
        self.finished_at = None
        self._touch()
        self._record_event("started")

    def set_transaction(
        self,
        transaction: ChangeTransaction,
    ) -> None:
        if transaction is None:
            raise ValueError("transaction cannot be None")

        self.transaction = transaction
        self.status = "waiting_for_approval"
        self.approved = False
        self._touch()
        self._record_event("transaction_set")

    def approve(self) -> bool:
        if self.transaction is None:
            self._record_event(
                "approval_rejected",
                note="Brak transakcji do zatwierdzenia.",
            )
            return False

        self.approved = True
        self.status = "approved"
        self._touch()
        self._record_event("approved")
        return True

    def mark_executing(self) -> None:
        if not self.can_execute():
            raise RuntimeError(
                "Session must be approved before execution"
            )

        self.status = "executing"
        self._touch()
        self._record_event("execution_started")

    def mark_completed(self) -> None:
        self.status = "completed"
        self.finished_at = datetime.now().isoformat()
        self._touch()
        self._record_event("completed")

    def mark_failed(self, error: str = "") -> None:
        self.status = "failed"
        self.finished_at = datetime.now().isoformat()

        clean_error = str(error).strip()
        if clean_error:
            self.notes.append(clean_error)

        self._touch()
        self._record_event("failed", note=clean_error)

    def mark_rolled_back(self) -> None:
        self.status = "rolled_back"
        self.finished_at = datetime.now().isoformat()
        self._touch()
        self._record_event("rolled_back")

    def cancel(self) -> None:
        self.status = "cancelled"
        self.approved = False
        self.transaction = None
        self.finished_at = datetime.now().isoformat()
        self._touch()
        self._record_event("cancelled")

    def add_note(self, note: str) -> None:
        clean_note = str(note).strip()
        if not clean_note:
            return

        self.notes.append(clean_note)
        self._touch()
        self._record_event("note_added", note=clean_note)

    def has_transaction(self) -> bool:
        return self.transaction is not None

    def can_execute(self) -> bool:
        return (
            self.transaction is not None
            and self.approved
            and self.status == "approved"
        )

    def is_terminal(self) -> bool:
        return self.status in {
            "completed",
            "failed",
            "rolled_back",
            "cancelled",
        }

    def duration_seconds(self) -> float | None:
        if self.started_at is None:
            return None

        try:
            started = datetime.fromisoformat(self.started_at)
            finished = (
                datetime.fromisoformat(self.finished_at)
                if self.finished_at
                else datetime.now()
            )
            return max(0.0, (finished - started).total_seconds())
        except (TypeError, ValueError):
            return None

    def to_dict(self) -> dict[str, Any]:
        transaction_data: Any = None

        if self.transaction is not None:
            if hasattr(self.transaction, "to_dict"):
                transaction_data = self.transaction.to_dict()
            else:
                transaction_data = {
                    "status": getattr(
                        self.transaction,
                        "status",
                        "",
                    ),
                    "summary": self.transaction.summary(),
                }

        return {
            "goal": self.goal,
            "target": self.target,
            "status": self.status,
            "approved": self.approved,
            "has_transaction": self.has_transaction(),
            "can_execute": self.can_execute(),
            "terminal": self.is_terminal(),
            "transaction": transaction_data,
            "notes": list(self.notes),
            "history": [
                event.to_dict()
                for event in self.history
            ],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "duration_seconds": self.duration_seconds(),
        }

    def summary(self) -> str:
        duration = self.duration_seconds()
        duration_text = (
            f"{duration:.3f} s"
            if duration is not None
            else "brak"
        )

        lines = [
            "DEVELOPER SESSION",
            f"Cel: {self.goal or 'brak'}",
            f"Target: {self.target or 'brak'}",
            f"Status: {self.status}",
            f"Zatwierdzona: {self.approved}",
            "Transakcja: "
            f"{'TAK' if self.transaction else 'NIE'}",
            f"Utworzono: {self.created_at}",
            f"Rozpoczęto: {self.started_at or 'brak'}",
            f"Zakończono: {self.finished_at or 'brak'}",
            f"Czas trwania: {duration_text}",
            f"Liczba zdarzeń: {len(self.history)}",
            f"Zaktualizowano: {self.updated_at}",
        ]

        if self.transaction:
            lines.append("")
            lines.append(self.transaction.summary())

        if self.notes:
            lines.append("")
            lines.append("Notatki:")
            for note in self.notes[-20:]:
                lines.append(f"- {note}")

        if self.history:
            lines.append("")
            lines.append("Ostatnie zdarzenia:")
            for event in self.history[-10:]:
                line = (
                    f"- {event.timestamp} | "
                    f"{event.event} | {event.status}"
                )
                if event.note:
                    line += f" | {event.note}"
                lines.append(line)

        return "\n".join(lines)

    def _record_event(
        self,
        event: str,
        *,
        note: str = "",
    ) -> None:
        self.history.append(
            SessionEvent(
                event=event,
                status=self.status,
                timestamp=datetime.now().isoformat(),
                note=note,
            )
        )

    def _touch(self) -> None:
        self.updated_at = datetime.now().isoformat()
