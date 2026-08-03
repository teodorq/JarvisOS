from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths

from .autonomous_diagnostics_models import AutonomousDiagnostic


class AutonomousDiagnosticsStore:
    """Atomic, bounded history of autonomy diagnostics and repairs."""

    def __init__(
        self,
        project_root: str | Path,
        *,
        max_records: int = 500,
        max_repairs: int = 500,
    ) -> None:
        self.paths = ProjectPaths.from_value(project_root)
        self.max_records = min(2000, max(50, int(max_records)))
        self.max_repairs = min(2000, max(50, int(max_repairs)))
        self.path = self.paths.autodev_data / "autonomous_diagnostics.json"
        self._store = JsonStore(self.path, self._default_payload)

    def save_diagnostic(
        self,
        diagnostic: AutonomousDiagnostic | dict[str, Any],
    ) -> dict[str, Any]:
        value = (
            diagnostic.to_dict()
            if isinstance(diagnostic, AutonomousDiagnostic)
            else AutonomousDiagnostic.from_dict(dict(diagnostic)).to_dict()
        )
        value = self._compact_diagnostic(value)
        diagnostic_id = str(value.get("diagnostic_id", "")).strip()
        if not diagnostic_id:
            raise ValueError("Diagnostyka wymaga diagnostic_id.")
        payload = self.load()
        payload["records"][diagnostic_id] = value
        order = payload["order"]
        if diagnostic_id in order:
            order.remove(diagnostic_id)
        order.append(diagnostic_id)
        while len(order) > self.max_records:
            removed = order.pop(0)
            payload["records"].pop(removed, None)
        payload["updated_at"] = self._now()
        self._store.save(payload)
        return dict(value)

    def get(self, diagnostic_id: str) -> dict[str, Any] | None:
        value = self.load()["records"].get(str(diagnostic_id).strip())
        return dict(value) if isinstance(value, dict) else None

    def latest_for_job(self, job_id: str) -> dict[str, Any] | None:
        key = str(job_id).strip()
        for item in self.list_recent(limit=self.max_records):
            if str(item.get("job_id", "")) == key:
                return item
        return None

    def latest_for_run(self, run_id: str) -> dict[str, Any] | None:
        key = str(run_id).strip()
        for item in self.list_recent(limit=self.max_records):
            if str(item.get("autonomy_run_id", "")) == key:
                return item
        return None

    def list_recent(
        self,
        *,
        limit: int = 20,
        category: str = "",
    ) -> list[dict[str, Any]]:
        payload = self.load()
        wanted = str(category).strip().upper()
        selected = payload["order"][-min(self.max_records, max(1, int(limit) * 5)):]
        result: list[dict[str, Any]] = []
        for diagnostic_id in reversed(selected):
            item = payload["records"].get(diagnostic_id)
            if not isinstance(item, dict):
                continue
            if wanted and str(item.get("category", "")).upper() != wanted:
                continue
            result.append(dict(item))
            if len(result) >= max(1, int(limit)):
                break
        return result

    def save_repair(self, repair: dict[str, Any]) -> dict[str, Any]:
        value = self._compact_repair(dict(repair))
        repair_id = str(value.get("repair_id", "")).strip()
        if not repair_id:
            raise ValueError("Naprawa wymaga repair_id.")
        payload = self.load()
        payload["repairs"][repair_id] = value
        order = payload["repair_order"]
        if repair_id in order:
            order.remove(repair_id)
        order.append(repair_id)
        while len(order) > self.max_repairs:
            removed = order.pop(0)
            payload["repairs"].pop(removed, None)
        payload["updated_at"] = self._now()
        self._store.save(payload)
        return dict(value)

    def list_repairs(self, *, limit: int = 20) -> list[dict[str, Any]]:
        payload = self.load()
        selected = payload["repair_order"][-max(1, int(limit)):]
        return [
            dict(payload["repairs"][repair_id])
            for repair_id in reversed(selected)
            if isinstance(payload["repairs"].get(repair_id), dict)
        ]

    def summary(self) -> dict[str, Any]:
        payload = self.load()
        counts: dict[str, int] = {}
        repairable = 0
        for item in payload["records"].values():
            if not isinstance(item, dict):
                continue
            category = str(item.get("category", "UNKNOWN")).upper()
            counts[category] = counts.get(category, 0) + 1
            repairable += int(bool(item.get("repairable", False)))
        return {
            "records": len(payload["records"]),
            "repairs": len(payload["repairs"]),
            "repairable": repairable,
            "counts": counts,
            "path": str(self.path),
        }

    def load(self) -> dict[str, Any]:
        return self._payload(self._store.load())

    @staticmethod
    def _default_payload() -> dict[str, Any]:
        return {
            "version": 1,
            "updated_at": "",
            "records": {},
            "order": [],
            "repairs": {},
            "repair_order": [],
        }

    @classmethod
    def _payload(cls, value: Any) -> dict[str, Any]:
        source = dict(value) if isinstance(value, dict) else {}
        records = source.get("records", {})
        repairs = source.get("repairs", {})
        records = records if isinstance(records, dict) else {}
        repairs = repairs if isinstance(repairs, dict) else {}
        normalized_records = {
            str(key): cls._compact_diagnostic(dict(item))
            for key, item in records.items()
            if isinstance(item, dict)
        }
        normalized_repairs = {
            str(key): cls._compact_repair(dict(item))
            for key, item in repairs.items()
            if isinstance(item, dict)
        }
        order = [
            str(item)
            for item in source.get("order", [])
            if str(item) in normalized_records
        ] if isinstance(source.get("order"), list) else []
        repair_order = [
            str(item)
            for item in source.get("repair_order", [])
            if str(item) in normalized_repairs
        ] if isinstance(source.get("repair_order"), list) else []
        for key in normalized_records:
            if key not in order:
                order.append(key)
        for key in normalized_repairs:
            if key not in repair_order:
                repair_order.append(key)
        return {
            "version": 1,
            "updated_at": str(source.get("updated_at", "")),
            "records": normalized_records,
            "order": order,
            "repairs": normalized_repairs,
            "repair_order": repair_order,
        }

    @staticmethod
    def _compact_diagnostic(value: dict[str, Any]) -> dict[str, Any]:
        result = dict(value)
        for key, limit in (
            ("summary", 2000),
            ("root_cause", 5000),
            ("traceback", 12000),
            ("stdout", 12000),
            ("stderr", 12000),
        ):
            result[key] = str(result.get(key, ""))[:limit]
        for key, limit in (
            ("errors", 50),
            ("files", 100),
            ("statuses", 100),
            ("suggested_actions", 20),
        ):
            items = result.get(key, [])
            result[key] = [str(item)[:2000] for item in items[:limit]] \
                if isinstance(items, list) else []
        result["evidence"] = AutonomousDiagnosticsStore._bounded_mapping(
            result.get("evidence"), depth=0
        )
        result["metadata"] = AutonomousDiagnosticsStore._bounded_mapping(
            result.get("metadata"), depth=0
        )
        return result

    @staticmethod
    def _compact_repair(value: dict[str, Any]) -> dict[str, Any]:
        result = dict(value)
        result["errors"] = [
            str(item)[:2000] for item in result.get("errors", [])[:20]
        ] if isinstance(result.get("errors"), list) else []
        result["actions"] = [
            str(item)[:1000] for item in result.get("actions", [])[:20]
        ] if isinstance(result.get("actions"), list) else []
        result["metadata"] = AutonomousDiagnosticsStore._bounded_mapping(
            result.get("metadata"), depth=0
        )
        return result

    @staticmethod
    def _bounded_mapping(value: Any, *, depth: int) -> Any:
        if depth > 4:
            return "<depth-limit>"
        if isinstance(value, dict):
            return {
                str(key)[:100]: AutonomousDiagnosticsStore._bounded_mapping(
                    item, depth=depth + 1
                )
                for key, item in list(value.items())[:50]
            }
        if isinstance(value, list):
            return [
                AutonomousDiagnosticsStore._bounded_mapping(
                    item, depth=depth + 1
                )
                for item in value[:50]
            ]
        if isinstance(value, str):
            return value[:4000]
        if isinstance(value, (bool, int, float)) or value is None:
            return value
        return str(value)[:1000]

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
