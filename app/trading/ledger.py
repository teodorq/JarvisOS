"""Atomic local ledger with a tamper-evident audit chain."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import threading
from typing import Any, Callable, TypeVar

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root
from app.trading.policy import PaperTradingPolicy


T = TypeVar("T")

_LEDGER_LOCKS_GUARD = threading.Lock()
_LEDGER_LOCKS: dict[str, threading.RLock] = {}


def _shared_ledger_lock(path: Path) -> threading.RLock:
    key = str(path).casefold()
    with _LEDGER_LOCKS_GUARD:
        return _LEDGER_LOCKS.setdefault(key, threading.RLock())


class PaperTradingLedger:
    """Persist simulated account state; never stores broker credentials."""

    MAX_FILLS = 10_000
    MAX_REJECTIONS = 2_000
    MAX_PROCESSED_ORDERS = 12_000
    MAX_AUDIT_EVENTS = 20_000

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        policy: PaperTradingPolicy | None = None,
    ) -> None:
        self.policy = policy or PaperTradingPolicy()
        root = resolve_project_root(project_root)
        self.path = root / "data" / "trading" / "paper_ledger.json"
        self.store = JsonStore(self.path, self._default)
        self._lock = _shared_ledger_lock(self.path)

    def _default(self) -> dict[str, Any]:
        initial_cash = str(self.policy.initial_cash)
        return {
            "schema_version": 1,
            "mode": "PAPER_ONLY",
            "base_currency": self.policy.base_currency,
            "initial_cash": initial_cash,
            "cash": initial_cash,
            "realized_pnl_total": "0",
            "positions": {},
            "fills": [],
            "rejections": [],
            "processed_orders": {},
            "audit": [],
            "kill_switch": {"active": False, "reason": "", "changed_at": ""},
            "session_date": "",
            "day_start_equity": initial_cash,
            "orders_today": 0,
        }

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return deepcopy(self._normalized(self.store.load()))

    def transaction(self, operation: Callable[[dict[str, Any]], T]) -> T:
        with self._lock:
            state = self._normalized(self.store.load())
            result = operation(state)
            self._trim(state)
            self.store.save(state)
            return result

    def append_event(
        self,
        state: dict[str, Any],
        event_type: str,
        details: dict[str, Any],
        *,
        created_at: datetime | None = None,
    ) -> dict[str, Any]:
        audit = list(state.get("audit", []) or [])
        previous_hash = str(audit[-1].get("event_hash", "")) if audit else ""
        event = {
            "sequence": len(audit) + 1,
            "event_type": str(event_type or "UNKNOWN")[:80],
            "created_at": (
                created_at or datetime.now(timezone.utc)
            ).astimezone(timezone.utc).isoformat(),
            "details": deepcopy(dict(details or {})),
            "previous_hash": previous_hash,
        }
        event["event_hash"] = self._event_hash(event)
        audit.append(event)
        state["audit"] = audit
        return deepcopy(event)

    @classmethod
    def verify_audit(cls, state: dict[str, Any]) -> bool:
        previous_hash = ""
        for index, raw in enumerate(list(state.get("audit", []) or []), 1):
            event = dict(raw or {})
            if int(event.get("sequence", 0) or 0) != index:
                return False
            if str(event.get("previous_hash", "")) != previous_hash:
                return False
            expected = cls._event_hash(event)
            if str(event.get("event_hash", "")) != expected:
                return False
            previous_hash = expected
        return True

    @staticmethod
    def _event_hash(event: dict[str, Any]) -> str:
        payload = {
            key: event.get(key)
            for key in (
                "sequence",
                "event_type",
                "created_at",
                "details",
                "previous_hash",
            )
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    def _normalized(self, value: object) -> dict[str, Any]:
        state = self._default()
        if isinstance(value, dict):
            for key in state:
                if key in value:
                    state[key] = deepcopy(value[key])
        state["schema_version"] = 1
        state["mode"] = (
            "PAPER_ONLY"
            if str(state.get("mode", "")).upper() == "PAPER_ONLY"
            else "INVALID"
        )
        state["base_currency"] = str(state.get("base_currency", "")).upper()
        state["positions"] = dict(state.get("positions", {}) or {})
        state["fills"] = [
            dict(item) for item in list(state.get("fills", []) or [])
            if isinstance(item, dict)
        ]
        state["rejections"] = [
            dict(item) for item in list(state.get("rejections", []) or [])
            if isinstance(item, dict)
        ]
        state["processed_orders"] = dict(state.get("processed_orders", {}) or {})
        state["audit"] = [
            dict(item) for item in list(state.get("audit", []) or [])
            if isinstance(item, dict)
        ]
        state["kill_switch"] = dict(state.get("kill_switch", {}) or {})
        state["orders_today"] = max(0, int(state.get("orders_today", 0) or 0))
        return state

    def _trim(self, state: dict[str, Any]) -> None:
        state["fills"] = list(state.get("fills", []) or [])[-self.MAX_FILLS :]
        state["rejections"] = list(
            state.get("rejections", []) or []
        )[-self.MAX_REJECTIONS :]
        processed = dict(state.get("processed_orders", {}) or {})
        if len(processed) > self.MAX_PROCESSED_ORDERS:
            keep = list(processed)[-self.MAX_PROCESSED_ORDERS :]
            processed = {key: processed[key] for key in keep}
        state["processed_orders"] = processed
        audit = list(state.get("audit", []) or [])
        if len(audit) > self.MAX_AUDIT_EVENTS:
            audit = audit[-self.MAX_AUDIT_EVENTS :]
            previous_hash = ""
            rebuilt: list[dict[str, Any]] = []
            for index, raw in enumerate(audit, 1):
                event = dict(raw)
                event["sequence"] = index
                event["previous_hash"] = previous_hash
                event["event_hash"] = self._event_hash(event)
                previous_hash = event["event_hash"]
                rebuilt.append(event)
            state["audit"] = rebuilt


__all__ = ["PaperTradingLedger"]
