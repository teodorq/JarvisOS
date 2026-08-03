from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path
import re
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root
from app.productivity.common import clean_text, new_id, sha256_file, utc_now


_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")


class LocalMailCenter:
    """B106 local drafts and outbox exports; never sends over the network."""

    def __init__(self, project_root: str | Path | None = None) -> None:
        self.root = resolve_project_root(project_root)
        self.store = JsonStore(
            self.root / "data" / "productivity" / "mail_center.json",
            self._default,
        )

    @staticmethod
    def _default() -> dict[str, Any]:
        return {
            "version": "1.0",
            "drafts": {},
            "active_draft_id": "",
            "exports": [],
            "updated_at": "",
        }

    def create_draft(
        self,
        recipient: str,
        subject: str,
        body: str,
        *,
        priority: str = "NORMAL",
    ) -> dict[str, Any]:
        address = clean_text(recipient, limit=254)
        if not _EMAIL.fullmatch(address):
            raise ValueError("Nieprawidłowy adres odbiorcy.")
        title = clean_text(subject, limit=200)
        content = str(body).strip()[:20000]
        if not title or not content:
            raise ValueError("Temat i treść szkicu są wymagane.")
        normalized_priority = str(priority).upper().strip()
        if normalized_priority not in {"LOW", "NORMAL", "HIGH"}:
            normalized_priority = "NORMAL"
        now = utc_now()
        draft = {
            "draft_id": new_id("mail"),
            "recipient": address,
            "subject": title,
            "body": content,
            "priority": normalized_priority,
            "status": "DRAFT",
            "created_at": now,
            "updated_at": now,
            "export_path": "",
            "sha256": "",
        }
        data = self._load()
        drafts = dict(data.get("drafts", {}) or {})
        drafts[draft["draft_id"]] = draft
        data.update({"drafts": drafts, "active_draft_id": draft["draft_id"], "updated_at": now})
        self.store.save(data)
        return draft

    def mark_ready(self, draft_id: str = "") -> dict[str, Any]:
        data = self._load()
        draft = self._require_draft(data, draft_id)
        if draft.get("status") == "EXPORTED":
            return draft
        draft["status"] = "READY_FOR_EXPORT"
        draft["updated_at"] = utc_now()
        self._save_draft(data, draft)
        return draft

    def export_ready(self, draft_id: str = "") -> dict[str, Any]:
        data = self._load()
        draft = self._require_draft(data, draft_id)
        if draft.get("status") not in {"READY_FOR_EXPORT", "EXPORTED"}:
            raise ValueError("Najpierw oznacz szkic jako gotowy do eksportu.")
        outbox = self.root / "AI_PLIKI" / "mail_outbox"
        outbox.mkdir(parents=True, exist_ok=True)
        path = outbox / f"{draft['draft_id']}.eml"
        message = EmailMessage()
        message["From"] = "jarvis-local@localhost"
        message["To"] = str(draft["recipient"])
        message["Subject"] = str(draft["subject"])
        message["X-Priority"] = {"HIGH": "1", "NORMAL": "3", "LOW": "5"}[str(draft["priority"])]
        message["X-JARVIS-Delivery"] = "LOCAL_EXPORT_ONLY"
        message.set_content(str(draft["body"]))
        path.write_bytes(message.as_bytes())
        draft.update({
            "status": "EXPORTED",
            "export_path": str(path),
            "sha256": sha256_file(path),
            "updated_at": utc_now(),
        })
        exports = list(data.get("exports", []) or [])
        exports.append({"draft_id": draft["draft_id"], "path": str(path), "sha256": draft["sha256"]})
        data["exports"] = exports[-500:]
        self._save_draft(data, draft)
        return draft

    def verify_latest_export(self) -> bool:
        data = self._load()
        draft = self._require_draft(data, "")
        path = Path(str(draft.get("export_path", "")))
        return bool(path.is_file() and draft.get("sha256") == sha256_file(path))

    def status(self) -> dict[str, Any]:
        data = self._load()
        drafts = list(dict(data.get("drafts", {}) or {}).values())
        active = dict(dict(data.get("drafts", {}) or {}).get(data.get("active_draft_id", ""), {}) or {})
        return {
            "status": "LOCAL_MAIL_CENTER_READY",
            "draft_count": len(drafts),
            "ready_count": sum(item.get("status") == "READY_FOR_EXPORT" for item in drafts),
            "exported_count": sum(item.get("status") == "EXPORTED" for item in drafts),
            "high_priority_count": sum(item.get("priority") == "HIGH" for item in drafts),
            "active_draft": active,
            "remote_delivery": False,
            "outbox_path": str(self.root / "AI_PLIKI" / "mail_outbox"),
        }

    def _load(self) -> dict[str, Any]:
        value = self.store.load()
        return value if isinstance(value, dict) else self._default()

    @staticmethod
    def _require_draft(data: dict[str, Any], draft_id: str) -> dict[str, Any]:
        identity = draft_id or str(data.get("active_draft_id", ""))
        draft = dict(dict(data.get("drafts", {}) or {}).get(identity, {}) or {})
        if not draft:
            raise ValueError("Brak aktywnego szkicu B106.")
        return draft

    def _save_draft(self, data: dict[str, Any], draft: dict[str, Any]) -> None:
        drafts = dict(data.get("drafts", {}) or {})
        drafts[str(draft["draft_id"])] = draft
        data.update({"drafts": drafts, "active_draft_id": draft["draft_id"], "updated_at": utc_now()})
        self.store.save(data)
