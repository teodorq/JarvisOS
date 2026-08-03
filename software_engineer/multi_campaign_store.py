from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths

from .multi_campaign_models import MultiCampaignPortfolio


class MultiCampaignStore:
    """Atomic bounded storage for multi-campaign portfolios."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        max_records: int = 30,
    ) -> None:
        self.paths = ProjectPaths.from_value(project_root)
        self.max_records = max(10, int(max_records))
        self.path = self.paths.autodev_data / "multi_campaign_portfolios.json"
        self._store = JsonStore(
            self.path,
            lambda: {
                "version": 1,
                "updated_at": "",
                "portfolios": {},
                "order": [],
            },
        )

    def save(self, portfolio: MultiCampaignPortfolio) -> dict[str, Any]:
        portfolio.touch()
        payload = self._payload(self._store.load())
        portfolio_id = portfolio.portfolio_id
        stored = portfolio.to_dict()
        payload["portfolios"][portfolio_id] = stored
        order = payload["order"]
        if portfolio_id in order:
            order.remove(portfolio_id)
        order.append(portfolio_id)
        while len(order) > self.max_records:
            removed = order.pop(0)
            payload["portfolios"].pop(removed, None)
        payload["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._store.save(payload)
        return dict(stored)

    def get(self, portfolio_id: str) -> MultiCampaignPortfolio | None:
        payload = self._payload(self._store.load())
        value = payload["portfolios"].get(str(portfolio_id).strip())
        if not isinstance(value, dict):
            return None
        return MultiCampaignPortfolio.from_dict(value)

    def list_recent(self, *, limit: int = 20) -> list[dict[str, Any]]:
        payload = self._payload(self._store.load())
        safe_limit = min(self.max_records, max(1, int(limit)))
        selected = payload["order"][-safe_limit:]
        return [
            dict(payload["portfolios"][portfolio_id])
            for portfolio_id in reversed(selected)
            if isinstance(payload["portfolios"].get(portfolio_id), dict)
        ]

    @staticmethod
    def _payload(value: Any) -> dict[str, Any]:
        payload = dict(value) if isinstance(value, dict) else {}
        portfolios = payload.get("portfolios", {})
        order = payload.get("order", [])
        if not isinstance(portfolios, dict):
            portfolios = {}
        if not isinstance(order, list):
            order = []
        normalized = {
            str(key): dict(item)
            for key, item in portfolios.items()
            if isinstance(item, dict)
        }
        normalized_order = [
            str(portfolio_id)
            for portfolio_id in order
            if str(portfolio_id) in normalized
        ]
        for portfolio_id in normalized:
            if portfolio_id not in normalized_order:
                normalized_order.append(portfolio_id)
        return {
            "version": 1,
            "updated_at": str(payload.get("updated_at", "")),
            "portfolios": normalized,
            "order": normalized_order,
        }
