from __future__ import annotations

from datetime import timedelta
from typing import Any


class ExactConflictProposal:
    """Builds a read-only move proposal from the exact shown conflict."""

    def __init__(self, calendar: Any, analyzer: Any) -> None:
        self.calendar = calendar
        self.analyzer = analyzer

    def build(self, issue: dict[str, Any]) -> dict[str, Any]:
        first = dict(issue.get("first", {}) or {})
        second = dict(issue.get("second", {}) or {})
        expected = [first, second]
        if not all(str(item.get("id", "")).strip() for item in expected):
            raise ValueError("Brakuje dokładnego kontekstu konfliktu.")

        starts = [self.analyzer.dt(item.get("start_at")) for item in expected]
        ends = [self.analyzer.dt(item.get("end_at")) for item in expected]
        if any(value is None for value in starts + ends):
            raise ValueError("Nie udało się odczytać godzin konfliktu.")

        start_at = min(starts) - timedelta(days=1)
        end_at = max(ends) + timedelta(days=3)
        events = [
            dict(item) for item in list(self.calendar.find_events(
                "", start_at=start_at, end_at=end_at, max_results=100
            ) or [])
        ]
        live = {str(item.get("id", "")): item for item in events}
        current = [live.get(str(item["id"]), {}) for item in expected]
        if not all(
            self._same_event(actual, saved)
            for actual, saved in zip(current, expected)
        ):
            raise ValueError(
                "Konflikt zmienił się od czasu alertu. "
                "Poproś mnie o ponowne sprawdzenie kalendarza."
            )

        first_end = self.analyzer.dt(current[0].get("end_at"))
        second_start = self.analyzer.dt(current[1].get("start_at"))
        second_end = self.analyzer.dt(current[1].get("end_at"))
        if None in {first_end, second_start, second_end}:
            raise ValueError("Nie udało się odczytać aktualnych godzin konfliktu.")

        duration = max(
            5, int((second_end - second_start).total_seconds() // 60)
        )
        target = self.analyzer.next_free_start(
            events, str(current[1].get("id", "")), first_end, duration
        )
        return {
            "kind": "calendar_move",
            "issue_fingerprint": str(issue.get("fingerprint", "")),
            "event_id": str(current[1].get("id", "")),
            "event_title": str(current[1].get("title", "wydarzenie")),
            "event_start": str(current[1].get("start_at", "")),
            "event_end": str(current[1].get("end_at", "")),
            "new_when": target.isoformat(),
            "duration_minutes": duration,
            "proposal_live_verified": True,
            "proposal_read_only": True,
        }

    def status(self) -> dict[str, Any]:
        return {
            "status": "EXACT_SAFE_CONFLICT_PROPOSAL_READY",
            "live_calendar_read": True,
            "exact_alert_pair_required": True,
            "free_target_required": True,
            "automatic_writes": False,
        }

    def _same_event(
        self,
        actual: dict[str, Any],
        expected: dict[str, Any],
    ) -> bool:
        if not actual:
            return False
        return (
            str(actual.get("id", "")) == str(expected.get("id", ""))
            and self._title(actual.get("title")) == self._title(expected.get("title"))
            and self._same_time(actual.get("start_at"), expected.get("start_at"))
            and self._same_time(actual.get("end_at"), expected.get("end_at"))
        )

    def _same_time(self, first: object, second: object) -> bool:
        left, right = self.analyzer.dt(first), self.analyzer.dt(second)
        return (
            left is not None
            and right is not None
            and abs((left - right).total_seconds()) < 60
        )

    @staticmethod
    def _title(value: object) -> str:
        return " ".join(str(value or "").split()).casefold()
