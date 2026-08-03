from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from app.natural_actions.calendar_plan_guard import CalendarPlanStaleError
from app.natural_actions.calendar_result_verifier import (
    CalendarLiveResultVerifier,
    CalendarResultVerificationError,
)
from app.natural_actions.calendar_safe_retry import (
    CalendarOperationLedger,
    CalendarSafeMoveExecutor,
)
from app.natural_actions.models import NaturalActionRequest


class CalendarUndoStaleError(CalendarPlanStaleError):
    """The event no longer matches the verified move selected for undo."""


class CalendarUndoCoordinator:
    """Prepare and verify one safe undo of the latest confirmed calendar move."""

    NO_CHANGE = "Nie mam ostatniej zweryfikowanej zmiany kalendarza do cofnięcia."
    STALE = (
        "Nie mogę cofnąć tej zmiany, ponieważ wydarzenie zostało później "
        "zmienione w Google Calendar. Nie wykonałem żadnego zapisu."
    )
    UNVERIFIED = (
        "Google Calendar nie potwierdził cofnięcia zmiany. "
        "Nie zgłaszam sukcesu. Sprawdź kalendarz."
    )

    def __init__(
        self,
        context: Any,
        calendar: Any,
        analyzer: Any,
        verifier: CalendarLiveResultVerifier,
        ledger: CalendarOperationLedger,
        formatter: Any,
    ) -> None:
        self.context = context
        self.calendar = calendar
        self.analyzer = analyzer
        self.verifier = verifier
        self.ledger = ledger
        self.formatter = formatter

    def prepare(self, request: NaturalActionRequest) -> None:
        candidate = self.last_candidate()
        if not candidate:
            self._missing(request, self.NO_CHANGE)
            return
        if not self._live(candidate, target="moved"):
            self._missing(request, self.STALE)
            return
        request.slots.update(candidate)
        request.missing = []
        original = self.analyzer.dt(candidate.get("original_start"))
        request.confirmation = (
            f"Cofnąć ostatnią zmianę i przywrócić "
            f"„{candidate['event_title']}” {self.formatter.when(original)}?"
        )

    def execute(self, request: NaturalActionRequest) -> str:
        slots = dict(request.slots)
        key = str(slots.get("operation_key", "")).strip()
        receipt = self.ledger.receipt(key)
        if str(receipt.get("undo_status", "")) == "COMPLETED":
            if self._live(slots, target="original"):
                return "Ta zmiana została już cofnięta. Nie wykonałem jej ponownie."
            raise CalendarUndoStaleError(self.STALE)
        if str(receipt.get("status", "")) != "COMPLETED":
            raise ValueError(self.NO_CHANGE)
        if not self._live(slots, target="moved"):
            raise CalendarUndoStaleError(self.STALE)

        original = self.analyzer.dt(slots.get("original_start"))
        if original is None:
            raise ValueError(self.NO_CHANGE)
        duration = int(slots.get("duration_minutes", 60) or 60)
        event_id = str(slots.get("event_id", ""))
        title = str(slots.get("event_title", "wydarzenie"))
        try:
            result = self.calendar.update_event(
                event_id, title, original, duration_minutes=duration
            )
        except Exception:
            live = self._live(slots, target="original")
            if not live:
                raise CalendarResultVerificationError(self.UNVERIFIED) from None
        else:
            try:
                live = self.verifier.verify_move(
                    result,
                    event_id=event_id,
                    title=title,
                    start_at=original,
                    duration_minutes=duration,
                )
            except CalendarResultVerificationError:
                raise CalendarResultVerificationError(self.UNVERIFIED) from None
        self.ledger.update(
            key,
            undo_status="COMPLETED",
            undo_completed_at=datetime.now(timezone.utc).isoformat(),
            undo_live_start=str(live.get("start_at", "")),
            undo_live_end=str(live.get("end_at", "")),
        )
        self.context.forget_execution(slots.get("source_request_fingerprint"))
        actual = self.analyzer.dt(live.get("start_at"))
        return (
            f"Cofnąłem ostatnią zmianę. „{title}” jest "
            f"{self.formatter.when(actual)}. Sprawdziłem wynik w Google Calendar."
        )

    def last_candidate(self) -> dict[str, Any]:
        candidate = self._receipt_candidate(self._latest_receipt())
        if candidate:
            return candidate
        history = list(self.context.load().get("history", []) or [])
        for raw in reversed(history):
            item = dict(raw or {})
            if str(item.get("intent", "")) not in {
                "active_apply_suggestion", "active_conflict_move",
            }:
                continue
            candidate = self._candidate(dict(item.get("slots", {}) or []))
            if candidate:
                return candidate
        return {}

    def _latest_receipt(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        required = ("operation_key", "event_id", "original_start", "moved_start")
        for item in reversed(self.ledger._items()):
            updated = self.ledger._dt(item.get("updated_at"))
            valid = updated and now - updated <= self.ledger.TTL
            complete = str(item.get("status", "")) == "COMPLETED"
            open_undo = str(item.get("undo_status", "")) != "COMPLETED"
            if valid and complete and open_undo and all(
                str(item.get(name, "")).strip() for name in required
            ):
                return dict(item)
        return {}

    def _receipt_candidate(self, receipt: dict[str, Any]) -> dict[str, Any]:
        if not receipt:
            return {}
        original = self.analyzer.dt(receipt.get("original_start"))
        moved = self.analyzer.dt(receipt.get("moved_start"))
        if original is None or moved is None:
            return {}
        duration = max(5, min(int(receipt.get("duration_minutes", 60)), 1440))
        return {
            "kind": "calendar_undo",
            "operation_key": str(receipt.get("operation_key", "")),
            "event_id": str(receipt.get("event_id", "")),
            "event_title": str(receipt.get("event_title", "wydarzenie")),
            "original_start": original.isoformat(),
            "original_end": str(receipt.get("original_end", "")),
            "moved_start": moved.isoformat(),
            "moved_end": str(receipt.get("moved_end", "")),
            "duration_minutes": duration,
            "source_request_fingerprint": str(
                receipt.get("request_fingerprint", "")
            ),
        }

    def _candidate(self, slots: dict[str, Any]) -> dict[str, Any]:
        new_when = self.analyzer.dt(slots.get("new_when"))
        original = self.analyzer.dt(slots.get("event_start"))
        if new_when is None or original is None:
            return {}
        duration = max(5, min(int(slots.get("duration_minutes", 60)), 1440))
        key = CalendarSafeMoveExecutor.operation_key(slots, new_when, duration)
        receipt = self.ledger.receipt(key)
        if str(receipt.get("status", "")) != "COMPLETED":
            return {}
        if str(receipt.get("undo_status", "")) == "COMPLETED":
            return {}
        return {
            "kind": "calendar_undo",
            "operation_key": key,
            "event_id": str(slots.get("event_id", "")),
            "event_title": str(slots.get("event_title", "wydarzenie")),
            "original_start": original.isoformat(),
            "original_end": str(slots.get("event_end", "")),
            "moved_start": new_when.isoformat(),
            "moved_end": (new_when + timedelta(minutes=duration)).isoformat(),
            "duration_minutes": duration,
            "source_request_fingerprint": str(
                receipt.get("request_fingerprint", "")
            ),
        }

    def _live(self, slots: dict[str, Any], *, target: str) -> dict[str, Any]:
        start = self.analyzer.dt(slots.get(f"{target}_start"))
        if start is None:
            return {}
        return self.verifier.find_move(
            event_id=str(slots.get("event_id", "")),
            title=str(slots.get("event_title", "")),
            start_at=start,
            duration_minutes=int(slots.get("duration_minutes", 60) or 60),
        )

    @staticmethod
    def _missing(request: NaturalActionRequest, message: str) -> None:
        request.missing = ["calendar_undo"]
        request.clarification = message
