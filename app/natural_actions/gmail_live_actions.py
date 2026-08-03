from __future__ import annotations

from email.utils import parseaddr
from typing import Any

from app.natural_actions.models import NaturalActionRequest
from app.online_assistant.gmail_live_center import GmailLiveWorkflowCenter


class GmailLiveNaturalActions:
    """Natural Gmail search/read/reply flow with persistent exact context."""

    INTENTS = {"gmail_search", "gmail_read", "gmail_thread", "gmail_reply_draft"}
    READ_ONLY = {"gmail_search", "gmail_read", "gmail_thread"}

    def __init__(self, context: Any, online: Any) -> None:
        self.context = context
        self.online = online
        self.center = GmailLiveWorkflowCenter(
            getattr(online, "project_root", None),
            provider=online.provider,
            gmail=online.gmail,
        )
        setattr(online, "gmail_live", self.center)

    def adopt_selected_reply(self, request: NaturalActionRequest) -> None:
        if request.intent == "active_mail_reply" and self.center.resolve_message():
            request.intent = "gmail_reply_draft"

    def prepare(self, request: NaturalActionRequest) -> None:
        if request.intent == "gmail_search":
            request.slots.setdefault("query", "in:inbox")
            request.missing = []
            return
        message = self.center.resolve_message(request.slots.get("message_ref"))
        if not message:
            request.missing = ["message"]
            request.clarification = (
                "Najpierw znajdź wiadomość Gmail albo wskaż numer z wyników."
            )
            return
        request.slots.update({
            "message_id": str(message.get("id", "")),
            "thread_id": str(message.get("thread_id", "")),
            "message_subject": str(message.get("subject", "(bez tematu)")),
            "message_from": str(message.get("from", "nadawcy")),
        })
        if request.intent in self.READ_ONLY:
            request.missing = []
            return
        body = str(request.slots.get("body", "") or "").strip()
        if not body:
            request.missing = ["body"]
            request.clarification = (
                "Podaj treść odpowiedzi, na przykład: „Przygotuj odpowiedź: Dziękuję”."
            )
            return
        request.missing = []
        preview = self._clip(body, 140)
        request.confirmation = (
            f"Utworzyć szkic odpowiedzi na „{request.slots['message_subject']}” "
            f"do {request.slots['message_from']} o treści: „{preview}”?"
        )

    def execute(self, request: NaturalActionRequest) -> str:
        slots = request.slots
        if request.intent == "gmail_search":
            results = self.center.search(str(slots.get("query", "in:inbox")), 10)
            if not results:
                return "Nie znalazłem pasujących wiadomości Gmail."
            lines = [
                f"{index}. {self._sender(item.get('from'))} — "
                f"„{self._clip(item.get('subject') or '(bez tematu)', 110)}”"
                for index, item in enumerate(results[:5], start=1)
            ]
            return (
                f"Znalazłem {len(lines)} najnowszych wiadomości:\n"
                + "\n".join(lines)
                + "\nAby przeczytać wiadomość, powiedz na przykład: "
                "„Przeczytaj wiadomość numer 1”."
            )
        if request.intent == "gmail_read":
            message = self.center.read_message(str(slots["message_id"]))
            return self._message_text(message)
        if request.intent == "gmail_thread":
            selected = self.center.read_message(str(slots["message_id"]))
            thread = self.center.read_thread(str(slots["thread_id"]))
            messages = list(thread.get("messages", []) or [])
            count = len(messages)
            thread_text = self._thread_text(messages)
            if slots.get("include_full_message"):
                return (
                    self._message_text(selected)
                    + f" Cały wątek ma {count} {self._message_word(count)}. "
                    + thread_text
                ).strip()
            return f"Wątek ma {count} {self._message_word(count)}. {thread_text}".strip()
        result = self.center.create_reply_draft(
            str(slots["message_id"]), str(slots["body"])
        )
        slots.update({
            "draft_id": str(result.get("draft_id", "")),
            "recipient_ref": str(result.get("recipient", "odbiorcy")),
            "recipient_email": str(result.get("recipient", "")),
            "subject": str(result.get("subject", "Odpowiedź")),
        })
        return (
            f"Szkic odpowiedzi do {slots['recipient_ref']} z tematem "
            f"„{slots['subject']}” jest gotowy. Wiadomość nie została wysłana."
        )

    def status(self) -> dict[str, Any]:
        return {
            **self.center.status(),
            "search": True,
            "full_message_read": True,
            "combined_message_and_thread_read": True,
            "thread_read": True,
            "threaded_reply_draft": True,
            "natural_reply_body": True,
            "verified_send": True,
            "send_requires_confirmation": True,
        }

    @classmethod
    def _message_text(cls, message: dict[str, Any]) -> str:
        body = cls._clip(message.get("body") or message.get("snippet"), 1800)
        body = body or "Wiadomość nie zawiera czytelnej treści tekstowej."
        return (
            f"Wiadomość od {message.get('from', 'nieznanego nadawcy')}, "
            f"temat „{message.get('subject', '(bez tematu)')}”. Treść: {body}"
        )

    @classmethod
    def _thread_text(cls, messages: list[dict[str, Any]]) -> str:
        if not messages:
            return "Gmail nie zwrócił wiadomości w tym wątku."
        parts = [
            f"{index}) {item.get('from', 'nadawca')}: "
            f"{cls._clip(item.get('body') or item.get('snippet'), 650)}"
            for index, item in enumerate(messages[-8:], start=max(1, len(messages) - 7))
        ]
        return " | ".join(parts)

    @staticmethod
    def _sender(value: object) -> str:
        raw = " ".join(str(value or "").split())
        name, address = parseaddr(raw)
        if name and address:
            return f"{name} ({address})"
        return address or name or raw or "nieznany nadawca"

    @staticmethod
    def _message_word(count: int) -> str:
        return "wiadomość" if count == 1 else "wiadomości" if 2 <= count <= 4 else "wiadomości"

    @staticmethod
    def _clip(value: object, limit: int) -> str:
        clean = " ".join(str(value or "").split())
        return clean[:limit] + ("…" if len(clean) > limit else "")
