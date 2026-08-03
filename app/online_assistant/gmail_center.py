from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root
from app.online_assistant.common import utc_now
from app.online_assistant.google_workspace import GoogleWorkspaceProvider


class GmailOnlineCenter:
    """B126 real Gmail reads, drafts and explicit confirmed sending."""

    def __init__(self, project_root: str | Path | None = None, *, provider: Any | None = None) -> None:
        self.project_root = resolve_project_root(project_root)
        self.provider = provider or GoogleWorkspaceProvider(self.project_root)
        self.store = JsonStore(
            self.project_root / "data" / "online_assistant" / "gmail_history.json",
            lambda: {"operations": [], "updated_at": ""},
        )

    def latest(self, max_results: int = 10) -> list[dict[str, Any]]:
        messages = self.provider.list_gmail_messages(
            query="in:inbox", max_results=max_results
        )
        self._record("READ_INBOX", {"count": len(messages)})
        return messages

    def priority(self, max_results: int = 10) -> list[dict[str, Any]]:
        messages = self.provider.list_gmail_messages(
            query="in:inbox {is:important is:starred is:unread}",
            max_results=max_results,
        )
        self._record("READ_PRIORITY", {"count": len(messages)})
        return messages

    def create_draft(self, recipient: str, subject: str, body: str) -> dict[str, Any]:
        result = self.provider.create_gmail_draft(recipient, subject, body)
        self._record(
            "CREATE_DRAFT",
            {
                "draft_id": result.get("draft_id", ""),
                "recipient": recipient,
                "subject": subject,
            },
        )
        return result

    def send_draft(self, draft_id: str) -> dict[str, Any]:
        sender = getattr(self.provider, "send_gmail_draft_verified", None)
        result = (sender(draft_id) if callable(sender) else self.provider.send_gmail_draft(draft_id))
        self._record(
            "SEND_DRAFT",
            {"draft_id": draft_id, "message_id": result.get("message_id", ""), "verified": bool(result.get("verified", False))},
        )
        return result


    def last_draft(self) -> dict[str, Any]:
        data = self.store.load()
        operations = list(dict(data or {}).get("operations", []) or [])
        for item in reversed(operations):
            if str(item.get("action", "")) == "CREATE_DRAFT":
                return dict(item.get("details", {}) or {})
        return {}

    def daily_activity(self) -> dict[str, Any]:
        data = self.store.load()
        operations = list(dict(data or {}).get("operations", []) or [])
        created: set[str] = set()
        sent: set[str] = set()
        sent_today = 0
        today = datetime.now().astimezone().date()
        for item in operations:
            action = str(item.get("action", ""))
            details = dict(item.get("details", {}) or {})
            draft_id = str(details.get("draft_id", "") or "")
            if action == "CREATE_DRAFT" and draft_id:
                created.add(draft_id)
            if action == "SEND_DRAFT" and draft_id:
                sent.add(draft_id)
                try:
                    created_at = datetime.fromisoformat(
                        str(item.get("created_at", "")).replace("Z", "+00:00")
                    ).astimezone()
                    sent_today += int(created_at.date() == today)
                except (TypeError, ValueError):
                    pass
        return {
            "sent_today": sent_today,
            "pending_drafts": len(created - sent),
            "automatic_replies": 0,
        }

    def status(self) -> dict[str, Any]:
        data = self.store.load()
        operations = list(dict(data or {}).get("operations", []) or [])
        connection = self.provider.connection_status()
        return {
            "status": "REAL_GMAIL_READY" if connection["token_present"] else "REAL_GMAIL_AWAITING_CONNECTION",
            "connected": bool(connection["token_present"]),
            "operation_count": len(operations),
            "last_operation": dict(operations[-1]) if operations else {},
            "automatic_sending": False,
            "sending_requires_confirmation": True,
        }

    def _record(self, action: str, details: dict[str, Any]) -> None:
        data = self.store.load()
        if not isinstance(data, dict):
            data = {"operations": [], "updated_at": ""}
        operations = list(data.get("operations", []) or [])
        operations.append({"action": action, "details": details, "created_at": utc_now()})
        data.update({"operations": operations[-200:], "updated_at": utc_now()})
        self.store.save(data)
