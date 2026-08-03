from __future__ import annotations

from pathlib import Path
import re
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root
from app.online_assistant.common import clip, utc_now
from app.online_assistant.google_workspace import GoogleWorkspaceProvider


class GoogleDriveCenter:
    """B128 Drive metadata search, bounded local summaries and confirmed reports."""

    def __init__(self, project_root: str | Path | None = None, *, provider: Any | None = None) -> None:
        self.project_root = resolve_project_root(project_root)
        self.provider = provider or GoogleWorkspaceProvider(self.project_root)
        self.store = JsonStore(
            self.project_root / "data" / "online_assistant" / "drive_history.json",
            lambda: {"operations": [], "updated_at": ""},
        )

    def search(self, query: str, max_results: int = 20) -> list[dict[str, Any]]:
        results = self.provider.search_drive_files(query, max_results=max_results)
        self._record("SEARCH", {"query": clip(query, 200), "count": len(results)})
        return results

    def recent(self, max_results: int = 10) -> list[dict[str, Any]]:
        reader = getattr(self.provider, "list_recent_drive_files", None)
        if not callable(reader):
            return []
        results = list(reader(max_results=max_results) or [])
        self._record("READ_RECENT", {"count": len(results)})
        return results

    def summarize(self, file_id: str, mime_type: str, *, name: str = "") -> dict[str, Any]:
        text = self.provider.read_drive_text(file_id, mime_type)
        summary = self._summary(text)
        result = {
            "status": "GOOGLE_DRIVE_DOCUMENT_SUMMARIZED",
            "file_id": str(file_id),
            "name": str(name),
            "characters_read": len(text),
            "summary": summary,
        }
        self._record("SUMMARIZE", {"file_id": str(file_id), "name": clip(name, 200)})
        return result

    def create_report(self, name: str, content: str) -> dict[str, Any]:
        result = self.provider.create_drive_text_file(name, content)
        self._record("CREATE_REPORT", {"file_id": result.get("file_id", ""), "name": name})
        return result

    def status(self) -> dict[str, Any]:
        data = self.store.load()
        operations = list(dict(data or {}).get("operations", []) or [])
        connected = bool(self.provider.connection_status()["token_present"])
        return {
            "status": "REAL_GOOGLE_DRIVE_READY" if connected else "REAL_GOOGLE_DRIVE_AWAITING_CONNECTION",
            "connected": connected,
            "operation_count": len(operations),
            "last_operation": dict(operations[-1]) if operations else {},
            "writes_require_confirmation": True,
            "max_read_characters": 250_000,
        }

    @staticmethod
    def _summary(text: str) -> str:
        cleaned = re.sub(r"\s+", " ", str(text)).strip()
        if not cleaned:
            return "Dokument nie zawiera tekstu możliwego do podsumowania."
        sentences = re.split(r"(?<=[.!?])\s+", cleaned)
        selected = [sentence for sentence in sentences if len(sentence) >= 20][:6]
        if not selected:
            selected = [cleaned[:1200]]
        return clip(" ".join(selected), 1600)

    def _record(self, action: str, details: dict[str, Any]) -> None:
        data = self.store.load()
        if not isinstance(data, dict):
            data = {"operations": [], "updated_at": ""}
        operations = list(data.get("operations", []) or [])
        operations.append({"action": action, "details": details, "created_at": utc_now()})
        data.update({"operations": operations[-200:], "updated_at": utc_now()})
        self.store.save(data)
