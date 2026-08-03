from __future__ import annotations

from pathlib import Path
from typing import Any

from app.core.json_store import JsonStore
from app.core.project_paths import resolve_project_root
from app.online_assistant.common import OnlineAssistantError, utc_now
from app.online_assistant.gmail_draft_recovery import GmailDraftRecoveryService


class GmailLiveWorkflowCenter:
    """Persistent Gmail selection, full reads, reply drafts and send receipts."""

    def __init__(
        self, project_root: str | Path | None, *, provider: Any, gmail: Any
    ) -> None:
        self.project_root = resolve_project_root(project_root)
        self.provider = provider
        self.gmail = gmail
        self.recovery = GmailDraftRecoveryService(provider)
        self.store = JsonStore(
            self.project_root / "data" / "online_assistant" / "gmail_live_workflow.json",
            self._default,
        )

    @staticmethod
    def _default() -> dict[str, Any]:
        return {
            "version": "1.1", "last_query": "", "results": [],
            "selected_message": {}, "selected_thread": {},
            "last_draft": {}, "last_send": {}, "updated_at": "",
        }

    def search(self, query: str, max_results: int = 10) -> list[dict[str, Any]]:
        query = str(query or "in:inbox").strip() or "in:inbox"
        results = list(self.provider.list_gmail_messages(
            query=query, max_results=max_results
        ))
        selected = dict(results[0]) if results else {}
        data = self._load()
        data.update({
            "last_query": query,
            "results": results,
            "selected_message": selected,
            "selected_thread": {},
            "updated_at": utc_now(),
        })
        self.store.save(data)
        return results

    def resolve_message(self, reference: object = None) -> dict[str, Any]:
        data = self._load()
        results = list(data.get("results", []) or [])
        value = str(reference or "").strip()
        if value.isdigit() and 1 <= int(value) <= len(results):
            return dict(results[int(value) - 1])
        if value:
            folded = value.casefold()
            for item in results:
                haystack = " ".join(
                    str(item.get(key, "")) for key in ("id", "from", "subject")
                ).casefold()
                if folded in haystack:
                    return dict(item)
        selected = dict(data.get("selected_message", {}) or {})
        return selected or (dict(results[0]) if results else {})

    def read_message(self, message_id: str) -> dict[str, Any]:
        message = dict(self.provider.get_gmail_message(message_id) or {})
        if not message.get("id"):
            raise OnlineAssistantError("Gmail nie zwrócił wybranej wiadomości.")
        data = self._load()
        data.update({"selected_message": message, "updated_at": utc_now()})
        self.store.save(data)
        return message

    def read_thread(self, thread_id: str) -> dict[str, Any]:
        thread = dict(self.provider.get_gmail_thread(thread_id) or {})
        data = self._load()
        data.update({"selected_thread": thread, "updated_at": utc_now()})
        self.store.save(data)
        return thread

    def create_reply_draft(self, message_id: str, body: str) -> dict[str, Any]:
        body = str(body or "").strip()
        if not body:
            raise OnlineAssistantError("Treść odpowiedzi jest pusta.")
        result = dict(self.provider.create_gmail_reply_draft(message_id, body) or {})
        if not result.get("draft_id"):
            raise OnlineAssistantError("Gmail nie zwrócił identyfikatora szkicu.")
        details = {
            **result,
            "recipient_ref": result.get("recipient", "odbiorcy"),
            "recipient_email": result.get("recipient", ""),
            "body": body,
            "sent": False,
            "created_at": utc_now(),
        }
        recorder = getattr(self.gmail, "_record", None)
        if callable(recorder):
            recorder("CREATE_DRAFT", details)
        data = self._load()
        data.update({"last_draft": details, "updated_at": utc_now()})
        self.store.save(data)
        return details

    def resolve_sendable_draft(self) -> dict[str, Any]:
        data = self._load()
        draft = self.recovery.resolve(
            dict(data.get("last_draft", {}) or {}),
            dict(data.get("selected_message", {}) or {}),
        )
        if draft and draft != dict(data.get("last_draft", {}) or {}):
            data.update({"last_draft": draft, "updated_at": utc_now()})
            self.store.save(data)
        return draft

    def send_draft_verified(self, draft_id: str) -> dict[str, Any]:
        data = self._load()
        saved = dict(data.get("last_draft", {}) or {})
        draft = self.resolve_sendable_draft() or saved
        if draft.get("sent") and str(draft.get("draft_id", "")) == str(draft_id):
            raise OnlineAssistantError("Ta odpowiedź została już wysłana.")
        sender = getattr(self.provider, "send_gmail_draft_verified", None)
        if callable(sender):
            result = dict(sender(draft_id) or {})
        else:
            result = dict(self.gmail.send_draft(draft_id) or {})
            result.update({
                "verified": bool(result.get("message_id")),
                "compatibility_fallback": True,
            })
        if not result.get("verified"):
            raise OnlineAssistantError("Nie potwierdziłem wysłania wiadomości w Gmail.")
        if str(draft.get("draft_id", "")) == str(draft_id):
            draft.update({
                "sent": True,
                "sent_at": utc_now(),
                "sent_message_id": str(result.get("message_id", "")),
            })
        data.update({"last_draft": draft, "last_send": result, "updated_at": utc_now()})
        self.store.save(data)
        return result

    def last_draft(self) -> dict[str, Any]:
        return dict(self._load().get("last_draft", {}) or {})

    def status(self) -> dict[str, Any]:
        data = self._load()
        draft = dict(data.get("last_draft", {}) or {})
        return {
            "status": "GMAIL_LIVE_WORKFLOW_READY",
            "result_count": len(list(data.get("results", []) or [])),
            "selected_message": bool(data.get("selected_message")),
            "selected_thread": bool(data.get("selected_thread")),
            "draft_ready": bool(draft) and not bool(draft.get("sent")),
            "last_draft_sent": bool(draft.get("sent")),
            "last_send_verified": bool(dict(data.get("last_send", {}) or {}).get("verified")),
            "automatic_sending": False,
            "sending_requires_confirmation": True,
        }

    def _load(self) -> dict[str, Any]:
        value = self.store.load()
        data = self._default()
        if isinstance(value, dict):
            data.update(value)
        return data
