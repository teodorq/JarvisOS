from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root
from app.online_assistant.common import clip, fold_text, utc_now


class GmailWorkflowService:
    """B132 ranked inbox, drafts, archive and labels with explicit write gates."""

    PRIORITY_WORDS = (
        "pilne", "urgent", "ważne", "wazne", "faktura", "invoice",
        "termin", "deadline", "awaria", "problem", "payment", "płatność", "platnosc",
    )

    def __init__(self, project_root: str | Path | None = None, *, provider: Any, reliability: Any) -> None:
        self.project_root = resolve_project_root(project_root)
        self.provider = provider
        self.reliability = reliability
        self.store = JsonStore(
            self.project_root / "data" / "online_assistant_v13" / "gmail_workflows.json",
            lambda: {"operations": [], "drafts": [], "updated_at": ""},
        )

    def briefing(self, max_results: int = 15) -> dict[str, Any]:
        read = self.reliability.read(
            "gmail_work_briefing",
            lambda: self.provider.list_gmail_messages(
                query="in:inbox newer_than:14d", max_results=max(1, min(int(max_results), 25))
            ),
        )
        ranked = []
        for message in list(read["value"] or []):
            item = dict(message or {})
            score, reasons = self._score(item)
            item.update({"priority_score": score, "priority_reasons": reasons})
            ranked.append(item)
        ranked.sort(key=lambda row: (row["priority_score"], row.get("date", "")), reverse=True)
        result = {
            "status": "GMAIL_WORKFLOW_BRIEFING_READY",
            "mode": read["mode"],
            "message_count": len(ranked),
            "messages": ranked[:10],
            "unread_count": sum(bool(row.get("unread")) for row in ranked),
            "important_count": sum(bool(row.get("important")) for row in ranked),
        }
        self._record("BRIEFING", {"count": len(ranked), "mode": read["mode"]})
        return result

    def create_draft(self, recipient: str, subject: str, body: str) -> dict[str, Any]:
        result = self.reliability.write(
            "gmail_create_draft",
            lambda: self.provider.create_gmail_draft(recipient, subject, body),
        )
        data = self._load()
        drafts = list(data.get("drafts", []) or [])
        drafts.append({
            "draft_id": result.get("draft_id", ""), "recipient": clip(recipient, 200),
            "subject": clip(subject, 240), "created_at": utc_now(), "status": "DRAFT",
        })
        data.update({"drafts": drafts[-100:], "updated_at": utc_now()})
        self.store.save(data)
        self._record("CREATE_DRAFT", {"draft_id": result.get("draft_id", "")})
        return result

    def send_draft(self, draft_id: str) -> dict[str, Any]:
        result = self.reliability.write(
            "gmail_send_draft", lambda: self.provider.send_gmail_draft(draft_id)
        )
        self._record("SEND_DRAFT", {"draft_id": clip(draft_id, 120)})
        return result

    def archive(self, message_id: str) -> dict[str, Any]:
        result = self.reliability.write(
            "gmail_archive", lambda: self.provider.archive_gmail_message(message_id)
        )
        self._record("ARCHIVE", {"message_id": clip(message_id, 120)})
        return result

    def add_label(self, message_id: str, label_name: str) -> dict[str, Any]:
        result = self.reliability.write(
            "gmail_add_label",
            lambda: self.provider.add_gmail_label(message_id, label_name),
        )
        self._record("ADD_LABEL", {
            "message_id": clip(message_id, 120), "label": clip(label_name, 120),
        })
        return result

    def status(self) -> dict[str, Any]:
        data = self._load()
        operations = list(data.get("operations", []) or [])
        return {
            "status": "GMAIL_WORKFLOWS_READY",
            "operation_count": len(operations),
            "draft_count": len(list(data.get("drafts", []) or [])),
            "last_operation": dict(operations[-1]) if operations else {},
            "writes_require_confirmation": True,
            "automatic_sending": False,
        }

    @classmethod
    def _score(cls, item: dict[str, Any]) -> tuple[int, list[str]]:
        score = 0
        reasons: list[str] = []
        if item.get("important"):
            score += 50
            reasons.append("IMPORTANT")
        if item.get("unread"):
            score += 25
            reasons.append("UNREAD")
        text = fold_text(f"{item.get('subject', '')} {item.get('snippet', '')}")
        hits = [word for word in cls.PRIORITY_WORDS if fold_text(word) in text]
        if hits:
            score += min(30, 10 * len(hits))
            reasons.append("KEYWORDS")
        return score, reasons

    def _record(self, action: str, details: dict[str, Any]) -> None:
        data = self._load()
        operations = list(data.get("operations", []) or [])
        operations.append({"action": action, "details": details, "created_at": utc_now()})
        data.update({"operations": operations[-250:], "updated_at": utc_now()})
        self.store.save(data)

    def _load(self) -> dict[str, Any]:
        data = self.store.load()
        return data if isinstance(data, dict) else {"operations": [], "drafts": [], "updated_at": ""}
