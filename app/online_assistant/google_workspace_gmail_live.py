from __future__ import annotations

import base64
from email.message import EmailMessage
from email.utils import parseaddr
from html import unescape
import re
from typing import Any

from app.online_assistant.common import OnlineAssistantError, header_value, safe_error


class GmailLiveProviderMixin:
    """Full Gmail reads, threaded reply drafts and verified sending."""

    def get_gmail_message(self, message_id: str) -> dict[str, Any]:
        message_id = str(message_id or "").strip()
        if not message_id:
            raise OnlineAssistantError("Podaj wiadomość Gmail do odczytania.")
        try:
            message = self._service("gmail", "v1").users().messages().get(
                userId="me", id=message_id, format="full"
            ).execute()
            return self._format_gmail_message(message)
        except Exception as error:
            raise OnlineAssistantError(
                f"Nie udało się odczytać wiadomości Gmail: {safe_error(error)}"
            ) from None

    def get_gmail_thread(self, thread_id: str) -> dict[str, Any]:
        thread_id = str(thread_id or "").strip()
        if not thread_id:
            raise OnlineAssistantError("Podaj wątek Gmail do odczytania.")
        try:
            result = self._service("gmail", "v1").users().threads().get(
                userId="me", id=thread_id, format="full"
            ).execute()
            messages = [
                self._format_gmail_message(item)
                for item in list(result.get("messages", []) or [])
            ]
            return {
                "thread_id": str(result.get("id", thread_id)),
                "history_id": str(result.get("historyId", "")),
                "messages": messages,
                "count": len(messages),
            }
        except Exception as error:
            raise OnlineAssistantError(
                f"Nie udało się odczytać wątku Gmail: {safe_error(error)}"
            ) from None

    def create_gmail_reply_draft(self, message_id: str, body: str) -> dict[str, Any]:
        original = self.get_gmail_message(message_id)
        _, recipient = parseaddr(original.get("reply_to") or original.get("from", ""))
        recipient = recipient or str(original.get("from", "")).strip()
        if "@" not in recipient:
            raise OnlineAssistantError("Nie udało się ustalić adresu odpowiedzi.")
        subject = str(original.get("subject", "") or "(bez tematu)").strip()
        if not subject.casefold().startswith("re:"):
            subject = f"Re: {subject}"
        message = EmailMessage()
        message["To"] = recipient
        message["Subject"] = subject[:240]
        source_id = str(original.get("rfc_message_id", "") or "").strip()
        references = str(original.get("references", "") or "").strip()
        if source_id:
            message["In-Reply-To"] = source_id
            message["References"] = " ".join(
                part for part in (references, source_id) if part
            )[-900:]
        message.set_content(str(body or "").strip()[:100_000])
        raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")
        try:
            result = self._service("gmail", "v1").users().drafts().create(
                userId="me",
                body={"message": {
                    "raw": raw,
                    "threadId": str(original.get("thread_id", "")),
                }},
            ).execute()
            return {
                "status": "GMAIL_REPLY_DRAFT_CREATED",
                "draft_id": str(result.get("id", "")),
                "message_id": str(dict(result.get("message", {}) or {}).get("id", "")),
                "source_message_id": str(original.get("id", message_id)),
                "thread_id": str(original.get("thread_id", "")),
                "recipient": recipient,
                "subject": subject,
            }
        except Exception as error:
            raise OnlineAssistantError(
                f"Nie udało się utworzyć szkicu odpowiedzi Gmail: {safe_error(error)}"
            ) from None

    def get_gmail_draft(self, draft_id: str) -> dict[str, Any]:
        draft_id = str(draft_id or "").strip()
        if not draft_id:
            raise OnlineAssistantError("Podaj szkic Gmail do odczytania.")
        try:
            draft = self._service("gmail", "v1").users().drafts().get(
                userId="me", id=draft_id, format="full"
            ).execute()
            message = self._format_gmail_message(dict(draft.get("message", {}) or {}))
            return {
                "draft_id": str(draft.get("id", draft_id)),
                "message_id": str(message.get("id", "")),
                "thread_id": str(message.get("thread_id", "")),
                "recipient": str(message.get("to", "")),
                "recipient_email": str(message.get("to", "")),
                "subject": str(message.get("subject", "(bez tematu)")),
                "body": str(message.get("body", "")),
                "labels": list(message.get("labels", []) or []),
            }
        except Exception as error:
            raise OnlineAssistantError(
                f"Nie udało się odczytać szkicu Gmail: {safe_error(error)}"
            ) from None

    def list_gmail_drafts(self, *, max_results: int = 20) -> list[dict[str, Any]]:
        try:
            service = self._service("gmail", "v1")
            result = service.users().drafts().list(
                userId="me", maxResults=max(1, min(int(max_results), 25))
            ).execute()
            return [self.get_gmail_draft(str(item.get("id", "")))
                    for item in list(result.get("drafts", []) or [])
                    if item.get("id")]
        except OnlineAssistantError:
            raise
        except Exception as error:
            raise OnlineAssistantError(
                f"Nie udało się odczytać szkiców Gmail: {safe_error(error)}"
            ) from None

    def send_gmail_draft_verified(self, draft_id: str) -> dict[str, Any]:
        sent = self.send_gmail_draft(draft_id)
        message_id = str(sent.get("message_id", "") or "").strip()
        if not message_id:
            raise OnlineAssistantError("Gmail nie zwrócił identyfikatora wysłanej wiadomości.")
        try:
            message = self._service("gmail", "v1").users().messages().get(
                userId="me", id=message_id, format="metadata"
            ).execute()
            labels = list(message.get("labelIds", []) or [])
            if "SENT" not in labels:
                raise OnlineAssistantError("Nie potwierdziłem wysłania wiadomości w Gmail.")
            return {
                **sent, "status": "GMAIL_DRAFT_SENT_VERIFIED",
                "verified": True, "labels": labels,
            }
        except OnlineAssistantError:
            raise
        except Exception as error:
            raise OnlineAssistantError(
                f"Nie udało się potwierdzić wysłania wiadomości: {safe_error(error)}"
            ) from None

    def _format_gmail_message(self, message: dict[str, Any]) -> dict[str, Any]:
        payload = dict(message.get("payload", {}) or {})
        headers = list(payload.get("headers", []) or [])
        message_id = str(message.get("id", ""))
        return {
            "id": message_id,
            "thread_id": str(message.get("threadId", "")),
            "from": header_value(headers, "From"),
            "to": header_value(headers, "To"),
            "reply_to": header_value(headers, "Reply-To"),
            "subject": header_value(headers, "Subject") or "(bez tematu)",
            "date": header_value(headers, "Date"),
            "rfc_message_id": header_value(headers, "Message-ID"),
            "references": header_value(headers, "References"),
            "snippet": str(message.get("snippet", ""))[:500],
            "body": self._gmail_body(message_id, payload),
            "labels": list(message.get("labelIds", []) or []),
        }

    def _gmail_body(self, message_id: str, payload: dict[str, Any]) -> str:
        plain: list[str] = []
        html: list[str] = []

        def visit(part: dict[str, Any]) -> None:
            mime = str(part.get("mimeType", "") or "").casefold()
            if mime in {"text/plain", "text/html"} or not part.get("parts"):
                text = self._part_text(message_id, part)
                if text:
                    (html if mime == "text/html" else plain).append(text)
            for child in list(part.get("parts", []) or []):
                visit(dict(child or {}))

        visit(payload)
        if plain:
            return "\n".join(plain).strip()[:100_000]
        if html:
            value = re.sub(r"(?is)<(?:script|style).*?>.*?</(?:script|style)>", " ", "\n".join(html))
            value = re.sub(r"(?s)<[^>]+>", " ", value)
            return " ".join(unescape(value).split())[:100_000]
        return ""

    def _part_text(self, message_id: str, part: dict[str, Any]) -> str:
        body = dict(part.get("body", {}) or {})
        data = str(body.get("data", "") or "")
        attachment_id = str(body.get("attachmentId", "") or "")
        if not data and attachment_id:
            try:
                attachment = self._service("gmail", "v1").users().messages().attachments().get(
                    userId="me", messageId=message_id, id=attachment_id
                ).execute()
                data = str(attachment.get("data", "") or "")
            except Exception:
                data = ""
        if not data:
            return ""
        try:
            raw = base64.urlsafe_b64decode(data + "=" * (-len(data) % 4))
        except Exception:
            return ""
        headers = list(part.get("headers", []) or [])
        content_type = header_value(headers, "Content-Type")
        match = re.search(r"charset=[\"']?([^;\"']+)", content_type, re.I)
        encodings = [match.group(1).strip()] if match else []
        encodings.extend(["utf-8", "cp1250", "latin-1"])
        for encoding in dict.fromkeys(encodings):
            try:
                return raw.decode(encoding)
            except (LookupError, UnicodeDecodeError):
                continue
        return raw.decode("utf-8", errors="replace")
