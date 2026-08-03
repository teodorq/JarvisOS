from __future__ import annotations

from typing import Any, Callable

from app.natural_actions.conflict_alert_context import ConflictAlertContext
from app.natural_actions.startup_conflict_notification import (
    StartupConflictNotificationPolicy,
)


class StartupConflictScanService:
    """Read-only calendar conflict scan performed once after client startup."""

    def __init__(
        self,
        snapshot_provider: Callable[[int], dict[str, Any]],
    ) -> None:
        self.snapshot_provider = snapshot_provider

    def scan(self) -> dict[str, Any]:
        snapshots = [self._snapshot(0), self._snapshot(1)]
        events = self._unique_events(
            list(snapshots[0].get("events", []) or [])
            + list(snapshots[1].get("events", []) or [])
        )
        contexts = ConflictAlertContext.analyze(events)
        fingerprint = StartupConflictNotificationPolicy.conflict_fingerprint(events)
        if not contexts:
            return {
                "should_show": False,
                "message": "",
                "level": "quiet",
                "speak": False,
                "conflict_count": 0,
                "fingerprint": "",
                "conflict_context": {},
                "automatic_writes": False,
                "scan_completed": True,
            }
        item = contexts[0]
        first = dict(item["first"])
        second = dict(item["second"])
        suffix = (
            f" Widzę jeszcze {len(contexts) - 1} "
            "dodatkowy konflikt."
            if len(contexts) > 1
            else ""
        )
        return {
            "should_show": True,
            "message": (
                f"Wykryłem konflikt w kalendarzu: „{first['title']}” i "
                f"„{second['title']}” nakładają się o {item['at']}."
                f"{suffix} Zapytaj: „Co mam zrobić z tym konfliktem?”"
            ),
            "level": "critical",
            "speak": False,
            "conflict_count": len(contexts),
            "fingerprint": fingerprint,
            "conflict_context": item,
            "automatic_writes": False,
            "scan_completed": True,
        }

    def status(self) -> dict[str, Any]:
        return {
            "status": "STARTUP_CONFLICT_SCAN_READY",
            "days_checked": 2,
            "automatic_writes": False,
            "silent_startup": True,
            "exact_conflict_context": True,
        }

    def _snapshot(self, offset: int) -> dict[str, Any]:
        try:
            value = self.snapshot_provider(offset)
        except Exception:
            return {"events": []}
        return dict(value or {})

    @staticmethod
    def _unique_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
        unique: dict[tuple[str, str, str, str], dict[str, Any]] = {}
        for raw in events:
            item = dict(raw)
            key = (
                str(item.get("id", "")),
                str(item.get("title", "")),
                str(item.get("start_at", "")),
                str(item.get("end_at", "")),
            )
            unique[key] = item
        return list(unique.values())
