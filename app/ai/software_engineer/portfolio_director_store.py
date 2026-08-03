from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths


class PortfolioDirectorStore:
    """Atomic bounded storage for autonomous director runs."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        max_records: int = 50,
    ) -> None:
        self.paths = ProjectPaths.from_value(project_root)
        self.max_records = min(200, max(10, int(max_records)))
        self.path = self.paths.autodev_data / "portfolio_director_runs.json"
        self._store = JsonStore(
            self.path,
            lambda: {
                "version": 1,
                "updated_at": "",
                "runs": {},
                "order": [],
            },
        )

    def save(self, run: dict[str, Any]) -> dict[str, Any]:
        value = dict(run)
        run_id = str(value.get("run_id", "")).strip()
        if not run_id:
            raise ValueError("Director run wymaga run_id.")
        payload = self._payload(self._store.load())
        value["updated_at"] = datetime.now(timezone.utc).isoformat()
        payload["runs"][run_id] = value
        order = payload["order"]
        if run_id in order:
            order.remove(run_id)
        order.append(run_id)
        while len(order) > self.max_records:
            removed = order.pop(0)
            payload["runs"].pop(removed, None)
        payload["updated_at"] = value["updated_at"]
        self._store.save(payload)
        return dict(value)

    def get(self, run_id: str) -> dict[str, Any] | None:
        payload = self._payload(self._store.load())
        value = payload["runs"].get(str(run_id).strip())
        return dict(value) if isinstance(value, dict) else None

    def latest_for_portfolio(self, portfolio_id: str) -> dict[str, Any] | None:
        target = str(portfolio_id).strip()
        for item in self.list_recent(limit=self.max_records):
            if str(item.get("portfolio_id", "")) == target:
                return item
        return None

    def list_recent(self, *, limit: int = 20) -> list[dict[str, Any]]:
        payload = self._payload(self._store.load())
        selected = payload["order"][-min(self.max_records, max(1, int(limit))):]
        return [
            dict(payload["runs"][run_id])
            for run_id in reversed(selected)
            if isinstance(payload["runs"].get(run_id), dict)
        ]

    @staticmethod
    def _payload(value: Any) -> dict[str, Any]:
        payload = dict(value) if isinstance(value, dict) else {}
        runs = payload.get("runs", {})
        order = payload.get("order", [])
        if not isinstance(runs, dict):
            runs = {}
        if not isinstance(order, list):
            order = []
        normalized = {
            str(key): dict(item)
            for key, item in runs.items()
            if isinstance(item, dict)
        }
        normalized_order = [
            str(run_id)
            for run_id in order
            if str(run_id) in normalized
        ]
        for run_id in normalized:
            if run_id not in normalized_order:
                normalized_order.append(run_id)
        return {
            "version": 1,
            "updated_at": str(payload.get("updated_at", "")),
            "runs": normalized,
            "order": normalized_order,
        }
