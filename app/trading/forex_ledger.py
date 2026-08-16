"""Atomic, tamper-evident ledger for autonomous Forex paper cycles."""

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


T = TypeVar("T")
_LOCKS_GUARD = threading.Lock()
_LOCKS: dict[str, threading.RLock] = {}


def _shared_lock(path: Path) -> threading.RLock:
    key = str(path).casefold()
    with _LOCKS_GUARD:
        return _LOCKS.setdefault(key, threading.RLock())


class ForexPaperLedger:
    """Persist paper positions and cycle outcomes; never stores credentials."""

    MAX_FILLS = 20_000
    MAX_REJECTIONS = 5_000
    MAX_CYCLES = 20_000
    MAX_AUDIT = 30_000

    def __init__(
        self,
        project_root: str | Path | None = None,
        *,
        initial_balance_pln: str = "100000",
    ) -> None:
        root = resolve_project_root(project_root)
        self.path = root / "data" / "trading" / "forex_paper_ledger.json"
        self.initial_balance_pln = str(initial_balance_pln)
        self.store = JsonStore(self.path, self._default)
        self._lock = _shared_lock(self.path)

    def _default(self) -> dict[str, Any]:
        return {
            "schema_version": 1,
            "mode": "FOREX_PAPER_ONLY",
            "account_currency": "PLN",
            "initial_balance_pln": self.initial_balance_pln,
            "balance_pln": self.initial_balance_pln,
            "daily_pnl_pln": "0",
            "session_date": "",
            "positions": {},
            "fills": [],
            "rejections": [],
            "processed_cycles": {},
            "audit": [],
            "kill_switch": {"active": False, "reason": "", "changed_at": ""},
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
    ) -> None:
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
        state["audit"] = audit + [event]

    @classmethod
    def verify_audit(cls, state: dict[str, Any]) -> bool:
        previous_hash = ""
        for sequence, raw in enumerate(list(state.get("audit", []) or []), 1):
            event = dict(raw or {})
            if int(event.get("sequence", 0) or 0) != sequence:
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
            "FOREX_PAPER_ONLY"
            if str(state.get("mode", "")).upper() == "FOREX_PAPER_ONLY"
            else "INVALID"
        )
        state["positions"] = dict(state.get("positions", {}) or {})
        state["fills"] = [
            dict(item) for item in list(state.get("fills", []) or [])
            if isinstance(item, dict)
        ]
        state["rejections"] = [
            dict(item) for item in list(state.get("rejections", []) or [])
            if isinstance(item, dict)
        ]
        state["processed_cycles"] = dict(
            state.get("processed_cycles", {}) or {}
        )
        state["audit"] = [
            dict(item) for item in list(state.get("audit", []) or [])
            if isinstance(item, dict)
        ]
        state["kill_switch"] = dict(state.get("kill_switch", {}) or {})
        return state

    def _trim(self, state: dict[str, Any]) -> None:
        state["fills"] = list(state.get("fills", []) or [])[-self.MAX_FILLS:]
        state["rejections"] = list(
            state.get("rejections", []) or []
        )[-self.MAX_REJECTIONS:]
        cycles = dict(state.get("processed_cycles", {}) or {})
        if len(cycles) > self.MAX_CYCLES:
            keys = list(cycles)[-self.MAX_CYCLES:]
            cycles = {key: cycles[key] for key in keys}
        state["processed_cycles"] = cycles
        audit = list(state.get("audit", []) or [])
        if len(audit) > self.MAX_AUDIT:
            audit = audit[-self.MAX_AUDIT:]
            previous_hash = ""
            for sequence, event in enumerate(audit, 1):
                event["sequence"] = sequence
                event["previous_hash"] = previous_hash
                event["event_hash"] = self._event_hash(event)
                previous_hash = event["event_hash"]
            state["audit"] = audit


__all__ = ["ForexPaperLedger"]
