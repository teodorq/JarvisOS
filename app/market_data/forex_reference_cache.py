"""Bounded, validated cache for slow-changing PAPER reference data only."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from app.core.json_store import JsonStore
from app.market_data.forex_models import EconomicCalendarSnapshot, EconomicEvent, PlnReferenceRate
from app.trading.models import TradingValidationError, aware_utc


class ForexReferenceCache:
    """Persist no-secret NBP/calendar snapshots; never persist market prices."""

    _SCHEMA_VERSION = 1
    _MAX_FILE_BYTES = 512 * 1024
    _MAX_EVENTS = 1_000

    def __init__(self, project_root: str | Path | None) -> None:
        self.path = (
            Path(project_root).resolve(strict=False)
            / "data" / "trading" / "market_data_reference_cache.json"
            if project_root is not None else None
        )
        self.store = (
            JsonStore(self.path, self._default, indent=None)
            if self.path is not None else None
        )

    @classmethod
    def _default(cls) -> dict[str, object]:
        return {"schema_version": cls._SCHEMA_VERSION}

    def save_nbp(self, value: PlnReferenceRate) -> None:
        self._update({"nbp": {
            "currency": value.currency,
            "midpoint_pln": str(value.midpoint_pln),
            "effective_date": value.effective_date.isoformat(),
            "fetched_at": value.fetched_at.isoformat(),
        }})

    def load_nbp(
        self, *, now: datetime, max_age_seconds: int,
        max_effective_age_days: int,
    ) -> PlnReferenceRate | None:
        row = self._section("nbp")
        if row is None:
            return None
        try:
            value = PlnReferenceRate(
                currency=row.get("currency"),
                midpoint_pln=row.get("midpoint_pln"),
                effective_date=datetime.fromisoformat(
                    str(row.get("effective_date", ""))
                ).date(),
                fetched_at=self._datetime(row.get("fetched_at")),
            )
        except (TypeError, ValueError, TradingValidationError):
            return None
        selected_now = aware_utc(now)
        fetched_age = (selected_now - value.fetched_at).total_seconds()
        effective_age = (selected_now.date() - value.effective_date).days
        if not 0 <= fetched_age <= max_age_seconds:
            return None
        if not 0 <= effective_age <= max_effective_age_days:
            return None
        return value

    def save_calendar(self, value: EconomicCalendarSnapshot) -> None:
        self._update({"calendar": {
            "provider": value.provider,
            "fetched_at": value.fetched_at.isoformat(),
            "coverage_start": value.coverage_start.isoformat(),
            "coverage_end": value.coverage_end.isoformat(),
            "events": [
                {
                    "event_at": item.event_at.isoformat(),
                    "title": item.title,
                    "currencies": list(item.currencies),
                    "importance": item.importance,
                    "block_start_at": (
                        item.block_start_at.isoformat()
                        if item.block_start_at is not None else None
                    ),
                    "block_end_at": (
                        item.block_end_at.isoformat()
                        if item.block_end_at is not None else None
                    ),
                }
                for item in value.events
            ],
        }})

    def load_calendar(
        self, *, now: datetime, max_age_seconds: int,
    ) -> EconomicCalendarSnapshot | None:
        row = self._section("calendar")
        if row is None:
            return None
        raw_events = row.get("events")
        if not isinstance(raw_events, list) or not 1 <= len(raw_events) <= self._MAX_EVENTS:
            return None
        try:
            events = tuple(self._event(item) for item in raw_events)
            value = EconomicCalendarSnapshot(
                provider=row.get("provider"),
                fetched_at=self._datetime(row.get("fetched_at")),
                coverage_start=self._datetime(row.get("coverage_start")),
                coverage_end=self._datetime(row.get("coverage_end")),
                events=events,
            )
        except (TypeError, ValueError, TradingValidationError):
            return None
        selected_now = aware_utc(now)
        age = (selected_now - value.fetched_at).total_seconds()
        if not 0 <= age <= max_age_seconds:
            return None
        if not value.coverage_start <= selected_now <= value.coverage_end:
            return None
        return value

    def _section(self, name: str) -> Mapping[str, Any] | None:
        if self.store is None or self.path is None:
            return None
        try:
            if not self.path.is_file() or self.path.stat().st_size > self._MAX_FILE_BYTES:
                return None
            payload = self.store.load()
        except OSError:
            return None
        if not isinstance(payload, dict):
            return None
        if payload.get("schema_version") != self._SCHEMA_VERSION:
            return None
        value = payload.get(name)
        return value if isinstance(value, dict) else None

    def _update(self, section: Mapping[str, object]) -> None:
        if self.store is None:
            return

        def merge(current: object) -> dict[str, object]:
            payload = dict(current) if isinstance(current, dict) else {}
            if payload.get("schema_version") != self._SCHEMA_VERSION:
                payload.clear()
            payload["schema_version"] = self._SCHEMA_VERSION
            payload.update(section)
            return payload

        try:
            self.store.update(merge)
        except (OSError, RuntimeError):
            return

    @classmethod
    def _event(cls, raw: object) -> EconomicEvent:
        if not isinstance(raw, dict):
            raise ValueError("invalid event")
        return EconomicEvent(
            event_at=cls._datetime(raw.get("event_at")),
            title=raw.get("title"),
            currencies=tuple(raw.get("currencies", ())),
            importance=raw.get("importance"),
            block_start_at=(
                cls._datetime(raw.get("block_start_at"))
                if raw.get("block_start_at") is not None else None
            ),
            block_end_at=(
                cls._datetime(raw.get("block_end_at"))
                if raw.get("block_end_at") is not None else None
            ),
        )

    @staticmethod
    def _datetime(value: object) -> datetime:
        parsed = datetime.fromisoformat(str(value or ""))
        if parsed.tzinfo is None or parsed.utcoffset() is None:
            raise ValueError("timezone required")
        return parsed.astimezone(timezone.utc)


__all__ = ["ForexReferenceCache"]
