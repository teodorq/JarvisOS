"""Persistent, deduplicated owner notifications for Forex PAPER activity."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root
from app.market_data.forex_environment import ForexDataSettings
from app.trading.forex_activity_journal import ForexPaperActivityJournal


class ForexPaperActivityFeed:
    """Deliver durable journal events one at a time through the safe UI policy."""

    MAX_RESULT_BYTES = 2_000_000

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        settings: ForexDataSettings | None = None,
    ) -> None:
        root = resolve_project_root(project_root)
        self.result_path = root / "data" / "trading" / "forex_paper_last.json"
        self.journal = ForexPaperActivityJournal(root)
        self.state = JsonStore(
            root / "data" / "trading" / "forex_activity_notifications.json",
            self._default_state,
        )
        self.settings = settings or ForexDataSettings.from_environment()

    @staticmethod
    def _default_state() -> dict[str, Any]:
        return {
            "schema_version": 2,
            "last_seen_sequence": 0,
            "notification_count": 0,
            "history_baseline_applied": False,
            "last_cycle_key": "",
        }

    def poll(self) -> dict[str, Any] | None:
        if not self._active():
            return None
        self._sync_latest_result()
        current = self._load_state()
        pending = self.journal.events(
            after_sequence=current["last_seen_sequence"],
            limit=1,
        )
        if not pending:
            return None
        event = pending[0]
        current["last_seen_sequence"] = int(event["sequence"])
        current["notification_count"] = min(
            1_000_000, int(current["notification_count"]) + 1
        )
        self.state.save(current)
        return self._display_event(event)

    def history(self, *, limit: int = 50) -> list[dict[str, Any]]:
        if self._active():
            self._sync_latest_result()
        current = self._load_state()
        result = []
        for event in self.journal.events(limit=limit, newest=True):
            item = dict(event)
            backfill = item.get("origin") == "LEDGER_BACKFILL"
            delivered = (
                backfill
                or int(item["sequence"]) <= int(current["last_seen_sequence"])
            )
            item["delivered"] = delivered
            item["delivery_status"] = (
                "HISTORIA" if backfill else "POKAZANE" if delivered else "OCZEKUJE"
            )
            result.append(item)
        return result

    def status(self) -> dict[str, Any]:
        if self._active():
            self._sync_latest_result()
        current = self._load_state()
        history = self.journal.events(
            limit=self.journal.MAX_EVENTS, newest=True
        )
        pending_count = sum(
            int(item["sequence"]) > int(current["last_seen_sequence"])
            and item.get("origin") != "LEDGER_BACKFILL"
            for item in history
        )
        journal = self.journal.status()
        return {
            "status": "FOREX_PAPER_ACTIVITY_READY",
            "enabled": self._active(),
            "notification_count": current["notification_count"],
            "history_event_count": journal["event_count"],
            "pending_count": pending_count,
            "last_seen_sequence": current["last_seen_sequence"],
            "last_health": journal["last_health"],
            "dropped_event_count": journal["dropped_event_count"],
            "voice_notifications": False,
            "broker_orders_sent": False,
            "live_orders_sent": False,
        }

    def _load_state(self) -> dict[str, Any]:
        current = self._normalize_state(self.state.load())
        events = self.journal.events(
            limit=self.journal.MAX_EVENTS, newest=True
        )
        changed = False
        if not current["history_baseline_applied"]:
            baseline = max(
                (
                    int(item["sequence"])
                    for item in events
                    if item.get("origin") == "LEDGER_BACKFILL"
                ),
                default=0,
            )
            current["last_seen_sequence"] = max(
                int(current["last_seen_sequence"]), baseline
            )
            current["history_baseline_applied"] = True
            changed = True
        legacy_cycle = current.get("last_cycle_key", "")
        if legacy_cycle:
            legacy_sequence = max(
                (
                    int(item["sequence"])
                    for item in events
                    if item.get("cycle_key") == legacy_cycle
                ),
                default=0,
            )
            current["last_seen_sequence"] = max(
                int(current["last_seen_sequence"]), legacy_sequence
            )
            current["last_cycle_key"] = ""
            changed = True
        if changed:
            self.state.save(current)
        return current

    def _sync_latest_result(self) -> None:
        payload = self._load_result()
        if payload is None:
            self.journal.initialize()
            return
        self.journal.record(payload)

    def _load_result(self) -> dict[str, Any] | None:
        try:
            size = self.result_path.stat().st_size
            if size <= 0 or size > self.MAX_RESULT_BYTES:
                return None
            value = json.loads(self.result_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return None
        return dict(value) if isinstance(value, dict) else None

    def _active(self) -> bool:
        return bool(
            self.settings.enabled
            and self.settings.paper_autopilot_enabled
            and self.settings.primary_provider == "MT5_DEMO"
        )

    @staticmethod
    def _display_event(event: dict[str, Any]) -> dict[str, Any]:
        return {
            "state": event.get("state", "brief"),
            "message": str(event.get("message", ""))[:420],
            "progress": 0,
            "requires_confirmation": False,
            "result_type": "FOREX_PAPER_ACTIVITY",
            "activity_sequence": int(event.get("sequence", 0) or 0),
            "activity_kind": str(event.get("kind", "ACTIVITY"))[:48],
            "occurred_at": str(event.get("occurred_at", ""))[:64],
            "history_backed": True,
        }

    @classmethod
    def _normalize_state(cls, value: object) -> dict[str, Any]:
        result = cls._default_state()
        if isinstance(value, dict):
            try:
                seen = int(value.get("last_seen_sequence", 0) or 0)
            except (TypeError, ValueError):
                seen = 0
            try:
                count = int(value.get("notification_count", 0) or 0)
            except (TypeError, ValueError):
                count = 0
            result["last_seen_sequence"] = max(0, seen)
            result["notification_count"] = max(0, min(count, 1_000_000))
            result["history_baseline_applied"] = bool(
                value.get("history_baseline_applied", False)
            )
            result["last_cycle_key"] = str(
                value.get("last_cycle_key", "")
            )[:192]
        return result


__all__ = ["ForexPaperActivityFeed"]
