from __future__ import annotations

from datetime import datetime
from pathlib import Path
import re
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root
from app.online_assistant.common import clip, utc_now


class DriveDocumentService:
    """B134 bounded Drive reads and versioned JARVIS-created documents."""

    def __init__(self, project_root: str | Path | None = None, *, provider: Any, reliability: Any) -> None:
        self.project_root = resolve_project_root(project_root)
        self.provider = provider
        self.reliability = reliability
        self.store = JsonStore(
            self.project_root / "data" / "online_assistant_v13" / "drive_documents.json",
            lambda: {"documents": [], "operations": [], "updated_at": ""},
        )

    def search(self, query: str, max_results: int = 20) -> dict[str, Any]:
        read = self.reliability.read(
            f"drive_search_{clip(query, 80)}",
            lambda: self.provider.search_drive_files(query, max_results=max_results),
        )
        files = list(read["value"] or [])
        self._record("SEARCH", {"query": clip(query, 160), "count": len(files), "mode": read["mode"]})
        return {"status": "DRIVE_DOCUMENT_SEARCH_READY", "mode": read["mode"], "files": files}

    def summarize(self, file_id: str, mime_type: str, *, name: str = "") -> dict[str, Any]:
        read = self.reliability.read(
            f"drive_text_{file_id}", lambda: self.provider.read_drive_text(file_id, mime_type)
        )
        text = str(read["value"] or "")[:250_000]
        summary = self._summary(text)
        self._record("SUMMARIZE", {"file_id": clip(file_id, 120), "mode": read["mode"]})
        return {
            "status": "DRIVE_DOCUMENT_SUMMARY_READY", "mode": read["mode"],
            "file_id": str(file_id), "name": clip(name, 240),
            "characters_read": len(text), "summary": summary,
        }

    def create_version(self, title: str, content: str) -> dict[str, Any]:
        clean_title = self._safe_name(title)
        data = self._load()
        previous = [row for row in list(data.get("documents", []) or []) if row.get("title") == clean_title]
        version = len(previous) + 1
        filename = f"{clean_title}_v{version:02d}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        result = self.reliability.write(
            "drive_create_version",
            lambda: self.provider.create_drive_text_file(filename, str(content)[:200_000]),
        )
        record = {
            "title": clean_title, "version": version, "file_id": result.get("file_id", ""),
            "name": result.get("name", filename), "created_at": utc_now(),
        }
        documents = list(data.get("documents", []) or [])
        documents.append(record)
        data.update({"documents": documents[-300:], "updated_at": utc_now()})
        self.store.save(data)
        self._record("CREATE_VERSION", record)
        return {**result, "version": version, "title": clean_title}

    def versions(self, title: str = "") -> list[dict[str, Any]]:
        documents = list(self._load().get("documents", []) or [])
        if title:
            target = self._safe_name(title).casefold()
            documents = [row for row in documents if str(row.get("title", "")).casefold() == target]
        return documents[-50:]

    def status(self) -> dict[str, Any]:
        data = self._load()
        operations = list(data.get("operations", []) or [])
        documents = list(data.get("documents", []) or [])
        return {
            "status": "DRIVE_DOCUMENTS_READY",
            "document_version_count": len(documents),
            "operation_count": len(operations),
            "last_document": dict(documents[-1]) if documents else {},
            "max_read_characters": 250_000,
            "max_write_characters": 200_000,
            "writes_require_confirmation": True,
        }

    @staticmethod
    def _summary(text: str) -> str:
        cleaned = re.sub(r"\s+", " ", str(text)).strip()
        if not cleaned:
            return "Dokument nie zawiera tekstu możliwego do podsumowania."
        sentences = re.split(r"(?<=[.!?])\s+", cleaned)
        selected = [sentence for sentence in sentences if len(sentence) >= 20][:8]
        return clip(" ".join(selected) if selected else cleaned, 1800)

    @staticmethod
    def _safe_name(value: str) -> str:
        cleaned = re.sub(r"[^A-Za-z0-9ąćęłńóśżźĄĆĘŁŃÓŚŻŹ _-]+", "", str(value)).strip()
        return (cleaned or "JARVIS_DOCUMENT").replace(" ", "_")[:120]

    def _record(self, action: str, details: dict[str, Any]) -> None:
        data = self._load()
        operations = list(data.get("operations", []) or [])
        operations.append({"action": action, "details": details, "created_at": utc_now()})
        data.update({"operations": operations[-250:], "updated_at": utc_now()})
        self.store.save(data)

    def _load(self) -> dict[str, Any]:
        data = self.store.load()
        return data if isinstance(data, dict) else {"documents": [], "operations": [], "updated_at": ""}
