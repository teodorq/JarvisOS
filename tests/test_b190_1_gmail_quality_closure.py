from __future__ import annotations

import base64
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.jarvis_experience.smart_task_loop import SmartTaskLoop
from app.natural_actions.gmail_live_understanding import (
    classify_gmail_live, extract_gmail_live_slots,
)
from app.natural_actions.planned_execution import PlannedNaturalActionExecutor
from app.natural_actions.service import NaturalActionService
from app.online_assistant.common import OnlineAssistantError
from app.online_assistant.google_workspace_gmail_live import GmailLiveProviderMixin
from tests.test_b186_b190_gmail_live_workflow import AssistantStub, FakeOnline


class B1901GmailQualityClosureTests(unittest.TestCase):
    def service(self, directory: str, online: FakeOnline | None = None):
        return NaturalActionService(directory, online=online or FakeOnline(directory))

    def test_exact_user_reply_phrase_extracts_body(self) -> None:
        text = "Przygotuj odpowiedź: Dziękuję, odezwę się jutro."
        self.assertEqual(classify_gmail_live(text)[0], "gmail_reply_draft")
        slots = extract_gmail_live_slots("gmail_reply_draft", text, {})
        self.assertEqual(slots["body"], "Dziękuję, odezwę się jutro")

    def test_combined_full_message_and_thread_read(self) -> None:
        with TemporaryDirectory() as directory:
            service = self.service(directory)
            service.handle("Znajdź ostatnią wiadomość od anna@example.com")
            response = service.handle("Przeczytaj całą wiadomość i wątek")
        self.assertIn("Pełna treść wiadomości", response)
        self.assertIn("Cały wątek ma 2 wiadomości", response)
        self.assertIn("Druga wiadomość", response)

    def test_exact_user_flow_creates_draft_then_sends_after_confirmation(self) -> None:
        with TemporaryDirectory() as directory:
            online = FakeOnline(directory)
            service = self.service(directory, online)
            service.handle("Znajdź ostatnią wiadomość od anna@example.com")
            service.handle("Przeczytaj całą wiadomość i wątek")
            reply = service.plan(
                "Przygotuj odpowiedź: Dziękuję, odezwę się jutro."
            )
            draft_response = PlannedNaturalActionExecutor.execute(
                AssistantStub(service), reply
            )
            send = service.plan("Wyślij tę odpowiedź")
            send_response = PlannedNaturalActionExecutor.execute(
                AssistantStub(service), send
            )
        self.assertEqual(reply["assistant_intent"], "gmail_reply_draft")
        self.assertTrue(reply["requires_confirmation"])
        self.assertEqual(
            reply["natural_slots"]["body"], "Dziękuję, odezwę się jutro"
        )
        self.assertIn("nie została wysłana", draft_response)
        self.assertEqual(send["assistant_intent"], "mail_send_existing")
        self.assertTrue(send["requires_confirmation"])
        self.assertIn("sprawdzony w Gmail", send_response)

    def test_new_search_replaces_old_selection(self) -> None:
        with TemporaryDirectory() as directory:
            online = FakeOnline(directory)
            service = self.service(directory, online)
            service.handle("Pokaż najnowsze maile Gmail")
            service.handle("Przeczytaj drugi mail")
            service.handle("Znajdź ostatnią wiadomość od anna@example.com")
            selected = service.runtime.gmail_live.center.resolve_message()
        self.assertEqual(selected["id"], "m1")

    def test_sent_reply_cannot_be_sent_again(self) -> None:
        with TemporaryDirectory() as directory:
            online = FakeOnline(directory)
            service = self.service(directory, online)
            service.handle("Znajdź ostatnią wiadomość od anna@example.com")
            reply = service.plan("Przygotuj odpowiedź: Test ponownej wysyłki")
            PlannedNaturalActionExecutor.execute(AssistantStub(service), reply)
            send = service.plan("Wyślij tę odpowiedź")
            PlannedNaturalActionExecutor.execute(AssistantStub(service), send)
            repeated = service.plan("Wyślij tę odpowiedź")
        self.assertFalse(repeated["requires_confirmation"])
        self.assertIn("już wysłana", repeated["clarification"])
        self.assertEqual(online.provider.sent, ["draft-reply-1"])

    def test_one_message_thread_uses_correct_polish_form(self) -> None:
        with TemporaryDirectory() as directory:
            online = FakeOnline(directory)
            online.provider.get_gmail_thread = lambda thread_id: {
                "thread_id": thread_id,
                "count": 1,
                "messages": [online.provider.get_gmail_message("m1")],
            }
            service = self.service(directory, online)
            service.handle("Znajdź ostatnią wiadomość od anna@example.com")
            response = service.handle("Pokaż cały wątek")
        self.assertIn("Wątek ma 1 wiadomość", response)

    def test_gmail_api_error_is_visible_without_technical_trace(self) -> None:
        class Brain:
            @staticmethod
            def execute(_thought):
                raise OnlineAssistantError("Nie udało się utworzyć szkicu Gmail.")

        loop = SmartTaskLoop(Brain(), lambda *_: {"allowed": True}, lambda _: True)
        outcome = loop.execute({"can_execute": True})
        self.assertEqual(outcome.status, "FAILED")
        self.assertEqual(outcome.message, "Nie udało się utworzyć szkicu Gmail.")


class _Operation:
    def __init__(self, value):
        self.value = value

    def execute(self):
        return self.value


class _Attachments:
    def get(self, **_kwargs):
        encoded = base64.urlsafe_b64encode("Załączona pełna treść".encode()).decode()
        return _Operation({"data": encoded})


class _Messages:
    def __init__(self, message):
        self.message = message

    def get(self, **_kwargs):
        return _Operation(self.message)

    def attachments(self):
        return _Attachments()


class _Users:
    def __init__(self, message):
        self.message = message

    def messages(self):
        return _Messages(self.message)


class _Service:
    def __init__(self, message):
        self.message = message

    def users(self):
        return _Users(self.message)


class _AttachmentProvider(GmailLiveProviderMixin):
    def __init__(self):
        self.message = {
            "id": "m-att", "threadId": "t-att", "snippet": "skrót",
            "payload": {
                "mimeType": "text/plain",
                "headers": [
                    {"name": "From", "value": "Anna <anna@example.com>"},
                    {"name": "Subject", "value": "Duża wiadomość"},
                    {"name": "Content-Type", "value": "text/plain; charset=utf-8"},
                ],
                "body": {"attachmentId": "a-1"},
            },
        }

    def _service(self, *_args):
        return _Service(self.message)


class GmailAttachmentBodyTests(unittest.TestCase):
    def test_full_body_can_be_loaded_from_gmail_attachment_part(self) -> None:
        message = _AttachmentProvider().get_gmail_message("m-att")
        self.assertEqual(message["body"], "Załączona pełna treść")


if __name__ == "__main__":
    unittest.main()
