from __future__ import annotations

from typing import Any

from app.online_assistant.common import OnlineAssistantError, safe_error


class GmailWriteProviderMixin:
    """B132 Gmail archive and label writes shared by the Workspace provider."""

    def archive_gmail_message(self, message_id: str) -> dict[str, Any]:
        if not str(message_id).strip():
            raise OnlineAssistantError("B132: podaj identyfikator wiadomości Gmail.")
        try:
            result = self._service("gmail", "v1").users().messages().modify(
                userId="me",
                id=str(message_id).strip(),
                body={"removeLabelIds": ["INBOX"]},
            ).execute()
            return {
                "status": "GMAIL_MESSAGE_ARCHIVED",
                "message_id": str(result.get("id", message_id)),
                "labels": list(result.get("labelIds", []) or []),
            }
        except Exception as error:
            raise OnlineAssistantError(
                f"B132: archiwizacja Gmail nie powiodła się: {safe_error(error)}"
            ) from None

    def add_gmail_label(self, message_id: str, label_name: str) -> dict[str, Any]:
        message_id = str(message_id).strip()
        label_name = str(label_name).strip()
        if not message_id or not label_name:
            raise OnlineAssistantError("B132: podaj identyfikator wiadomości i nazwę etykiety.")
        try:
            service = self._service("gmail", "v1")
            labels = list(
                service.users().labels().list(userId="me").execute().get("labels", []) or []
            )
            label = next(
                (
                    item for item in labels
                    if str(item.get("name", "")).casefold() == label_name.casefold()
                ),
                None,
            )
            if label is None:
                label = service.users().labels().create(
                    userId="me",
                    body={
                        "name": label_name[:225],
                        "labelListVisibility": "labelShow",
                        "messageListVisibility": "show",
                    },
                ).execute()
            result = service.users().messages().modify(
                userId="me",
                id=message_id,
                body={"addLabelIds": [str(label.get("id", ""))]},
            ).execute()
            return {
                "status": "GMAIL_LABEL_ADDED",
                "message_id": str(result.get("id", message_id)),
                "label": str(label.get("name", label_name)),
            }
        except Exception as error:
            raise OnlineAssistantError(
                f"B132: dodanie etykiety Gmail nie powiodło się: {safe_error(error)}"
            ) from None
