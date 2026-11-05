"""Strict transport and durable inbox for Azure PAPER activity events."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import re
import threading
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root


MAX_CLOUD_ACTIVITY_EVENTS = 32
_MAX_INBOX_EVENTS = 128
_EVENT_ID = re.compile(r"^[0-9a-f]{24}$")
_ALLOWED_KINDS = frozenset({
    "DATA_BLOCKED",
    "DATA_RECOVERED",
    "FOREX_PAPER_SAMPLE_REVIEW_READY",
    "FOREX_V2_FORWARD_REVIEW_READY",
    "FOREX_V3_FORWARD_EVIDENCE_BLOCKED",
    "FOREX_V3_FORWARD_PROGRESS",
    "FOREX_V3_SHADOW_FIRST_PLAN_RECORDED",
    "FOREX_V3_SHADOW_INITIALIZATION_READY",
    "FOREX_V3_SHADOW_PLAN_SAMPLE_READY",
    "POSITION_CLOSED",
    "POSITION_OPENED",
    "POSITION_PROTECTION_ATTENTION",
    "POSITION_PROTECTION_RECOVERED",
    "SAFETY_ATTENTION",
})


class ForexCloudActivityError(ValueError):
    """Raised when an Azure activity event is not strictly allowlisted."""


def _event(value: object) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise ForexCloudActivityError("cloud_activity: invalid_event")
    event_id = str(value.get("event_id", "")).strip().lower()
    if not _EVENT_ID.fullmatch(event_id):
        raise ForexCloudActivityError("cloud_activity: invalid_event_id")
    try:
        sequence = int(value.get("sequence", 0))
    except (TypeError, ValueError, OverflowError) as error:
        raise ForexCloudActivityError(
            "cloud_activity: invalid_sequence"
        ) from error
    if isinstance(value.get("sequence"), bool) or not 0 < sequence <= 1_000_000:
        raise ForexCloudActivityError("cloud_activity: invalid_sequence")
    kind = str(value.get("kind", "")).strip().upper()
    if kind not in _ALLOWED_KINDS:
        raise ForexCloudActivityError("cloud_activity: invalid_kind")
    state = str(value.get("state", "")).strip().lower()
    if state not in {"brief", "important"}:
        raise ForexCloudActivityError("cloud_activity: invalid_state")
    occurred_at = str(value.get("occurred_at", "")).strip()
    try:
        timestamp = datetime.fromisoformat(occurred_at.replace("Z", "+00:00"))
    except (TypeError, ValueError) as error:
        raise ForexCloudActivityError(
            "cloud_activity: invalid_timestamp"
        ) from error
    if timestamp.tzinfo is None or timestamp.utcoffset() is None:
        raise ForexCloudActivityError("cloud_activity: invalid_timestamp")
    message = " ".join(str(value.get("message", "")).split())
    if not message or len(message) > 420:
        raise ForexCloudActivityError("cloud_activity: invalid_message")
    return {
        "sequence": sequence,
        "event_id": event_id,
        "occurred_at": timestamp.astimezone(timezone.utc).isoformat(),
        "kind": kind,
        "state": state,
        "message": message,
        "progress": 0,
        "requires_confirmation": False,
        "result_type": "FOREX_PAPER_ACTIVITY",
    }


def sanitize_forex_cloud_activity_events(value: object) -> list[dict[str, Any]]:
    """Return a bounded, ordered and deduplicated safe event list."""

    if value in (None, []):
        return []
    if not isinstance(value, list) or len(value) > MAX_CLOUD_ACTIVITY_EVENTS:
        raise ForexCloudActivityError("cloud_activity: invalid_list")
    result = [_event(item) for item in value]
    if any(
        current["sequence"] >= following["sequence"]
        for current, following in zip(result, result[1:])
    ) or len({item["event_id"] for item in result}) != len(result):
        raise ForexCloudActivityError("cloud_activity: invalid_order")
    return result


class CloudForexActivityInbox:
    """Persist cloud activity locally and deliver every event at most once."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        root = resolve_project_root(project_root)
        self.store = JsonStore(
            root / "data" / "trading" / "forex_cloud_activity_inbox.json",
            self._default,
        )
        self._lock = threading.Lock()

    @staticmethod
    def _default() -> dict[str, Any]:
        return {"schema_version": 1, "events": [], "delivered_event_ids": []}

    def sync(self, value: object) -> int:
        incoming = sanitize_forex_cloud_activity_events(value)
        if not incoming:
            return 0
        with self._lock:
            state = self._load()
            known = {item["event_id"] for item in state["events"]}
            added = [item for item in incoming if item["event_id"] not in known]
            state["events"] = (state["events"] + added)[-_MAX_INBOX_EVENTS:]
            retained = {item["event_id"] for item in state["events"]}
            state["delivered_event_ids"] = [
                item for item in state["delivered_event_ids"] if item in retained
            ]
            self.store.save(state)
            return len(added)

    def poll(self) -> dict[str, Any] | None:
        with self._lock:
            state = self._load()
            delivered = set(state["delivered_event_ids"])
            event = next(
                (item for item in state["events"] if item["event_id"] not in delivered),
                None,
            )
            if event is None:
                return None
            state["delivered_event_ids"] = (
                state["delivered_event_ids"] + [event["event_id"]]
            )[-_MAX_INBOX_EVENTS:]
            self.store.save(state)
            return dict(event)

    def history(self, *, limit: int = 50) -> list[dict[str, Any]]:
        state = self._load()
        delivered = set(state["delivered_event_ids"])
        result = []
        for event in state["events"][-max(1, min(int(limit), 128)):]:
            item = dict(event)
            item["origin"] = "AZURE_PAPER_STATUS"
            item["delivered"] = item["event_id"] in delivered
            item["delivery_status"] = (
                "POKAZANE" if item["delivered"] else "OCZEKUJE"
            )
            result.append(item)
        return result

    def status(self) -> dict[str, int]:
        state = self._load()
        delivered = set(state["delivered_event_ids"])
        return {
            "event_count": len(state["events"]),
            "pending_count": sum(
                item["event_id"] not in delivered for item in state["events"]
            ),
            "notification_count": sum(
                item["event_id"] in delivered for item in state["events"]
            ),
        }

    def _load(self) -> dict[str, Any]:
        value = self.store.load()
        if not isinstance(value, dict):
            return self._default()
        raw_events = value.get("events", [])
        events: list[dict[str, Any]] = []
        if isinstance(raw_events, list):
            for item in raw_events[-_MAX_INBOX_EVENTS:]:
                try:
                    events.extend(sanitize_forex_cloud_activity_events([item]))
                except ForexCloudActivityError:
                    continue
        raw_delivered = value.get("delivered_event_ids", [])
        raw_delivered = raw_delivered if isinstance(raw_delivered, list) else []
        delivered = [
            str(item) for item in raw_delivered
            if _EVENT_ID.fullmatch(str(item))
        ][-_MAX_INBOX_EVENTS:]
        return {
            "schema_version": 1,
            "events": events,
            "delivered_event_ids": list(dict.fromkeys(delivered)),
        }


__all__ = [
    "CloudForexActivityInbox",
    "ForexCloudActivityError",
    "MAX_CLOUD_ACTIVITY_EVENTS",
    "sanitize_forex_cloud_activity_events",
]
