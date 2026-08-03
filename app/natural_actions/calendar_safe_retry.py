from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
import json
from typing import Any, Callable

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root
from app.natural_actions.calendar_plan_guard import (
    CalendarMovePlanGuard,
    CalendarPlanStaleError,
)
from app.natural_actions.calendar_result_verifier import (
    CalendarLiveResultVerifier,
    CalendarResultVerificationError,
)


class CalendarSafeRetryError(CalendarResultVerificationError):
    """A move cannot be retried because its live state is uncertain."""

    MESSAGE = (
        "Nie mogę bezpiecznie potwierdzić tej zmiany. "
        "Nie wykonam kolejnej próby bez ponownego sprawdzenia konfliktu."
    )


@dataclass(frozen=True)
class CalendarMoveOutcome:
    live: dict[str, Any]
    duplicate: bool = False
    recovered: bool = False
    attempts: int = 0


class CalendarOperationLedger:
    """Persistent bounded receipts for exact calendar move operations."""

    TTL = timedelta(hours=24)
    def __init__(self, project_root: object) -> None:
        root = resolve_project_root(project_root)
        self.store = JsonStore(
            root / "data" / "natural_actions" / "calendar_operations.json",
            lambda: {"version": "1.0", "operations": [], "updated_at": ""},
        )
    def receipt(self, key: str) -> dict[str, Any]:
        now = datetime.now(timezone.utc)
        for item in reversed(self._items()):
            if str(item.get("operation_key", "")) != key:
                continue
            updated = self._dt(item.get("updated_at"))
            return dict(item) if updated and now - updated <= self.TTL else {}
        return {}
    def update(self, key: str, **values: Any) -> dict[str, Any]:
        data = self._load()
        items = [
            dict(item) for item in list(data.get("operations", []) or [])
            if str(item.get("operation_key", "")) != key
        ]
        previous = self.receipt(key)
        previous.update(values)
        previous["operation_key"] = key
        previous["updated_at"] = self._now()
        items.append(previous)
        data["operations"] = items[-120:]
        data["updated_at"] = self._now()
        self.store.save(data)
        return previous
    def _items(self) -> list[dict[str, Any]]:
        return [dict(item) for item in self._load().get("operations", []) or []]

    def _load(self) -> dict[str, Any]:
        value = self.store.load()
        return dict(value) if isinstance(value, dict) else {"operations": []}
    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
    @staticmethod
    def _dt(value: object) -> datetime | None:
        try:
            parsed = datetime.fromisoformat(str(value))
        except (TypeError, ValueError):
            return None
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)


class CalendarSafeMoveExecutor:
    """Idempotent calendar move with one verified and bounded retry."""

    MAX_ATTEMPTS = 2

    def __init__(
        self,
        project_root: object,
        calendar: Any,
        analyzer: Any,
        plan_guard: CalendarMovePlanGuard,
        verifier: CalendarLiveResultVerifier,
        clear_suggestion: Callable[[], None] | None = None,
    ) -> None:
        self.calendar = calendar
        self.analyzer = analyzer
        self.plan_guard = plan_guard
        self.verifier = verifier
        self.ledger = CalendarOperationLedger(project_root)
        self.clear_suggestion = clear_suggestion

    def execute(
        self,
        slots: dict[str, Any],
        new_when: datetime,
        duration_minutes: int,
    ) -> CalendarMoveOutcome:
        key = self.ensure_operation_key(slots, new_when, duration_minutes)
        receipt = self.ledger.receipt(key)
        self.ledger.update(
            key, event_id=str(slots.get("event_id", "")),
            event_title=str(slots.get("event_title", "")),
            original_start=str(slots.get("event_start", "")),
            original_end=str(slots.get("event_end", "")),
            moved_start=new_when.isoformat(),
            moved_end=(new_when + timedelta(minutes=duration_minutes)).isoformat(),
            duration_minutes=int(duration_minutes),
            request_fingerprint=str(slots.get("request_fingerprint", "")),
        )
        completed = str(receipt.get("status", "")) == "COMPLETED"
        undone = str(receipt.get("undo_status", "")) == "COMPLETED"
        if completed and undone:
            self._validate_or_stale(key, slots, new_when, duration_minutes)
            receipt = self.ledger.update(
                key, status="READY", attempts=0, undo_status="",
                undo_completed_at="", undo_live_start="", undo_live_end="",
            )
        elif completed:
            live = self._live_target(slots, new_when, duration_minutes)
            if live:
                return CalendarMoveOutcome(
                    live, duplicate=True,
                    attempts=int(receipt.get("attempts", 0) or 0),
                )
            self._stale(key)

        if receipt:
            live = self._live_target(slots, new_when, duration_minutes)
            if live:
                self._complete(key, receipt, live)
                return CalendarMoveOutcome(
                    live, recovered=True,
                    attempts=int(receipt.get("attempts", 0) or 0),
                )
            if int(receipt.get("attempts", 0) or 0) >= self.MAX_ATTEMPTS:
                self._reject(key)

        self._validate_or_stale(key, slots, new_when, duration_minutes)
        return self._attempt(key, slots, new_when, duration_minutes)
    def ensure_operation_key(
        self,
        slots: dict[str, Any],
        new_when: datetime,
        duration_minutes: int,
    ) -> str:
        actual = self.operation_key(slots, new_when, duration_minutes)
        expected = str(slots.get("operation_key", "")).strip()
        if expected and not hmac.compare_digest(expected, actual):
            raise ValueError("Klucz przygotowanej operacji kalendarza jest niezgodny.")
        slots["operation_key"] = actual
        return actual

    @staticmethod
    def operation_key(
        slots: dict[str, Any],
        new_when: datetime,
        duration_minutes: int,
    ) -> str:
        raw = json.dumps({
            "event_id": str(slots.get("event_id", "")).strip(),
            "event_title": " ".join(str(slots.get("event_title", "")).split()).casefold(),
            "event_start": str(slots.get("event_start", "")),
            "event_end": str(slots.get("event_end", "")),
            "new_when": new_when.astimezone(timezone.utc).isoformat(),
            "duration_minutes": int(duration_minutes),
            "issue_fingerprint": str(slots.get("issue_fingerprint", "")),
        }, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:32]

    def _attempt(
        self,
        key: str,
        slots: dict[str, Any],
        new_when: datetime,
        duration_minutes: int,
    ) -> CalendarMoveOutcome:
        receipt = self.ledger.receipt(key)
        attempts = int(receipt.get("attempts", 0) or 0) + 1
        self.ledger.update(key, status="RUNNING", attempts=attempts)
        try:
            result = self.calendar.update_event(
                str(slots.get("event_id", "")),
                str(slots.get("event_title", "")),
                new_when,
                duration_minutes=duration_minutes,
            )
        except Exception:
            return self._recover_or_retry(
                key, slots, new_when, duration_minutes, attempts
            )
        try:
            live = self.verifier.verify_move(
                result,
                event_id=str(slots.get("event_id", "")),
                title=str(slots.get("event_title", "")),
                start_at=new_when,
                duration_minutes=duration_minutes,
            )
        except CalendarResultVerificationError:
            self.ledger.update(key, status="UNVERIFIED", attempts=attempts)
            raise
        self._complete(key, {"attempts": attempts}, live)
        return CalendarMoveOutcome(live, attempts=attempts)
    def _recover_or_retry(
        self,
        key: str,
        slots: dict[str, Any],
        new_when: datetime,
        duration_minutes: int,
        attempts: int,
    ) -> CalendarMoveOutcome:
        try:
            live = self._live_target(slots, new_when, duration_minutes)
        except Exception:
            self._reject(key)
        if live:
            self._complete(key, {"attempts": attempts}, live)
            return CalendarMoveOutcome(live, recovered=True, attempts=attempts)
        if attempts >= self.MAX_ATTEMPTS:
            self._reject(key)
        self._validate_or_stale(key, slots, new_when, duration_minutes)
        return self._attempt(key, slots, new_when, duration_minutes)
    def _live_target(
        self,
        slots: dict[str, Any],
        new_when: datetime,
        duration_minutes: int,
    ) -> dict[str, Any]:
        return self.verifier.find_move(
            event_id=str(slots.get("event_id", "")),
            title=str(slots.get("event_title", "")),
            start_at=new_when,
            duration_minutes=duration_minutes,
        )
    def _validate_or_stale(
        self,
        key: str,
        slots: dict[str, Any],
        new_when: datetime,
        duration_minutes: int,
    ) -> None:
        try:
            self.plan_guard.validate(slots, new_when, duration_minutes)
        except CalendarPlanStaleError:
            self.ledger.update(key, status="STALE")
            raise

    def _complete(
        self,
        key: str,
        receipt: dict[str, Any],
        live: dict[str, Any],
    ) -> None:
        self.ledger.update(
            key,
            status="COMPLETED",
            attempts=int(receipt.get("attempts", 0) or 0),
            event_id=str(live.get("id", "")),
            live_start=str(live.get("start_at", "")),
            live_end=str(live.get("end_at", "")),
        )

    def _stale(self, key: str) -> None:
        self.ledger.update(key, status="STALE")
        if self.clear_suggestion is not None:
            self.clear_suggestion()
        raise CalendarPlanStaleError(CalendarMovePlanGuard.MESSAGE)

    def _reject(self, key: str) -> None:
        self.ledger.update(key, status="UNVERIFIED")
        if self.clear_suggestion is not None:
            self.clear_suggestion()
        raise CalendarSafeRetryError(CalendarSafeRetryError.MESSAGE)
