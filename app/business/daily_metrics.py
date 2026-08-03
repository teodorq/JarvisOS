from __future__ import annotations

from datetime import date, datetime
from pathlib import Path
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root


class DailyBusinessMetrics:
    """Read-only contract for future sales, advertising and trading connectors."""

    SOURCE_FIELDS = {
        "sales": ("revenue", "amount"),
        "advertising": ("spend", "cost", "amount"),
        "trading": ("profit", "pnl", "net", "amount"),
    }

    def __init__(self, project_root: str | Path | None = None) -> None:
        root = resolve_project_root(project_root)
        self.store = JsonStore(
            root / "data" / "business" / "daily_metrics.json",
            self._default,
        )

    @staticmethod
    def _default() -> dict[str, Any]:
        return {
            "version": "1.0",
            "sources": {
                "sales": {"connected": False, "records": []},
                "advertising": {"connected": False, "records": []},
                "trading": {"connected": False, "records": []},
            },
        }

    def snapshot(self, day: date | None = None) -> dict[str, Any]:
        selected = day or datetime.now().astimezone().date()
        data = self.store.load()
        sources = dict((data if isinstance(data, dict) else {}).get("sources", {}) or {})
        return {
            name: self._source_snapshot(
                name, dict(sources.get(name, {}) or {}), selected
            )
            for name in self.SOURCE_FIELDS
        }

    def _source_snapshot(
        self, name: str, source: dict[str, Any], selected: date
    ) -> dict[str, Any]:
        records = [
            dict(item) for item in list(source.get("records", []) or [])
            if self._record_day(item) == selected
        ]
        totals: dict[str, float] = {}
        for record in records:
            amount = self._amount(record, self.SOURCE_FIELDS[name])
            if amount is None:
                continue
            currency = str(record.get("currency", "PLN") or "PLN").upper()
            totals[currency] = round(totals.get(currency, 0.0) + amount, 2)
        return {
            "connected": bool(source.get("connected", False)),
            "record_count": len(records),
            "totals": totals,
            "records": records[:100],
            "dashboard_url": self._safe_url(source.get("dashboard_url")),
        }

    @staticmethod
    def _record_day(record: object) -> date | None:
        value = dict(record or {}) if isinstance(record, dict) else {}
        raw = value.get("created_at") or value.get("date") or value.get("day")
        try:
            return datetime.fromisoformat(str(raw).replace("Z", "+00:00")).date()
        except (TypeError, ValueError):
            try:
                return date.fromisoformat(str(raw)[:10])
            except (TypeError, ValueError):
                return None

    @staticmethod
    def _amount(record: dict[str, Any], fields: tuple[str, ...]) -> float | None:
        for field in fields:
            if field not in record:
                continue
            try:
                return round(float(str(record[field]).replace(",", ".")), 2)
            except (TypeError, ValueError):
                continue
        return None

    @staticmethod
    def _safe_url(value: object) -> str:
        url = str(value or "").strip()
        return url if url.startswith(("https://", "http://")) else ""


__all__ = ["DailyBusinessMetrics"]
