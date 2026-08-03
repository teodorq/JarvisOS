from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any
import uuid

from app.core.json_store import JsonStore
from app.core.project_paths import ProjectPaths


class BusinessAuditCenter:
    """B84 bounded local audit journal with deterministic exports."""

    MAX_EVENTS = 1000
    MAX_EXPORTS = 50

    def __init__(self, project_root: str | Path) -> None:
        self.paths = ProjectPaths.from_value(project_root)
        self.path = self.paths.data / "business" / "audit_center.json"
        self.export_dir = self.paths.data / "business" / "audit_exports"
        self._store = JsonStore(self.path, self._default_payload)

    def ensure(self) -> dict[str, Any]:
        payload = self._normalize(self._store.load())
        self._store.save(payload)
        return payload

    def record(
        self,
        action: str,
        *,
        category: str = "BUSINESS",
        decision: str = "OBSERVE",
        detail: str = "",
        actor: str = "Kacper",
        metadata: dict[str, Any] | None = None,
        source_key: str = "",
    ) -> dict[str, Any]:
        payload = self.ensure()
        normalized_source = str(source_key).strip()
        if normalized_source and normalized_source in payload["source_keys"]:
            return self.status()
        event = {
            "event_id": uuid.uuid4().hex,
            "timestamp": self._now(),
            "category": self._text(category, "BUSINESS", 60).upper(),
            "action": self._text(action, "EVENT", 100).upper(),
            "decision": self._text(decision, "OBSERVE", 40).upper(),
            "actor": self._text(actor, "Kacper", 80),
            "detail": self._text(detail, "", 500),
            "metadata": self._safe_metadata(metadata),
            "source_key": normalized_source[:128],
        }
        payload["events"].append(event)
        payload["events"] = payload["events"][-self.MAX_EVENTS :]
        if normalized_source:
            payload["source_keys"].append(normalized_source)
            payload["source_keys"] = payload["source_keys"][-self.MAX_EVENTS :]
        self._store.save(payload)
        response = self.status()
        response["status"] = "BUSINESS_AUDIT_EVENT_RECORDED"
        response["event"] = event
        response["decision"] = "RECORDED"
        return response

    def sync_access_events(self, access_status: dict[str, Any]) -> dict[str, Any]:
        events = access_status.get("audit_events", [])
        if not isinstance(events, list):
            return self.status()
        for item in events:
            if not isinstance(item, dict):
                continue
            source = json.dumps(item, sort_keys=True, ensure_ascii=False)
            source_key = "B83:" + hashlib.sha256(source.encode("utf-8")).hexdigest()
            self.record(
                str(item.get("action", "ACCESS_CONTROL")),
                category="ACCESS_CONTROL",
                decision=str(item.get("decision", "OBSERVE")),
                detail=str(item.get("detail", "")),
                actor=str(item.get("role", access_status.get("active_role", "UNKNOWN"))),
                metadata={"timestamp": item.get("timestamp")},
                source_key=source_key,
            )
        return self.status()

    def status(self) -> dict[str, Any]:
        payload = self.ensure()
        events = list(payload["events"])
        decision_counts = Counter(str(item.get("decision", "UNKNOWN")) for item in events)
        category_counts = Counter(str(item.get("category", "UNKNOWN")) for item in events)
        return {
            "success": True,
            "status": "BUSINESS_AUDIT_CENTER_STATUS",
            "operation": "business_audit_center",
            "stage": "B84",
            "runtime": {
                "phase": "READY",
                "running": False,
                "paused": False,
                "cycles_completed": len(events),
                "last_decision": "READY",
            },
            "event_count": len(events),
            "decision_counts": dict(decision_counts),
            "category_counts": dict(category_counts),
            "recent_events": events[-50:][::-1],
            "exports": list(payload["exports"][-10:]),
            "export_directory": str(self.export_dir),
            "decision": "READY",
            "reason": "Lokalny dziennik audytu jest aktywny i ograniczony.",
            "report_path": str(self.path),
            "errors": [],
        }

    def export_report(self) -> dict[str, Any]:
        payload = self.ensure()
        self.export_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        json_path = self.export_dir / f"JARVIS_AUDIT_{stamp}.json"
        text_path = self.export_dir / f"JARVIS_AUDIT_{stamp}.txt"
        report = {
            "schema_version": 1,
            "type": "JARVIS_BUSINESS_AUDIT_REPORT",
            "exported_at": self._now(),
            "event_count": len(payload["events"]),
            "events": payload["events"],
        }
        temporary = json_path.with_suffix(".json.tmp")
        temporary.write_text(
            json.dumps(report, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        temporary.replace(json_path)
        lines = [
            "JARVIS OS — RAPORT AUDYTU",
            f"Eksport: {report['exported_at']}",
            f"Zdarzenia: {report['event_count']}",
            "",
        ]
        for item in payload["events"]:
            lines.append(
                " | ".join(
                    str(value)
                    for value in (
                        item.get("timestamp", ""),
                        item.get("category", ""),
                        item.get("action", ""),
                        item.get("decision", ""),
                        item.get("actor", ""),
                        item.get("detail", ""),
                    )
                )
            )
        text_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        export = {
            "timestamp": report["exported_at"],
            "json_path": str(json_path),
            "text_path": str(text_path),
            "event_count": report["event_count"],
        }
        payload["exports"].append(export)
        payload["exports"] = payload["exports"][-self.MAX_EXPORTS :]
        self._store.save(payload)
        response = self.status()
        response.update({
            "status": "BUSINESS_AUDIT_REPORT_EXPORTED",
            "export": export,
            "decision": "EXPORTED",
            "reason": "Raport audytu zapisano lokalnie w JSON i TXT.",
        })
        return response

    def _default_payload(self) -> dict[str, Any]:
        return {"schema_version": 1, "events": [], "source_keys": [], "exports": []}

    def _normalize(self, payload: Any) -> dict[str, Any]:
        value = dict(payload or {}) if isinstance(payload, dict) else {}
        events = [item for item in value.get("events", []) if isinstance(item, dict)]
        exports = [item for item in value.get("exports", []) if isinstance(item, dict)]
        keys = [str(item) for item in value.get("source_keys", []) if str(item).strip()]
        return {
            "schema_version": 1,
            "events": events[-self.MAX_EVENTS :],
            "source_keys": keys[-self.MAX_EVENTS :],
            "exports": exports[-self.MAX_EXPORTS :],
        }

    @staticmethod
    def _safe_metadata(value: dict[str, Any] | None) -> dict[str, Any]:
        metadata = dict(value or {})
        try:
            return json.loads(json.dumps(metadata, ensure_ascii=False, default=str))
        except (TypeError, ValueError):
            return {}

    @staticmethod
    def _text(value: Any, default: str, limit: int) -> str:
        text = " ".join(str(value or default).split())
        return text[:limit]

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
