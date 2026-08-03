from __future__ import annotations

import base64
from email import message_from_bytes
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.natural_actions.gmail_reliability_gate import GmailReliabilityGate
from app.natural_actions.planned_execution import PlannedNaturalActionExecutor
from app.natural_actions.service import NaturalActionService
from app.online_assistant.common import OnlineAssistantError
from app.online_assistant.google_workspace_gmail_live import GmailLiveProviderMixin


class FakeGmail:
    def __init__(self) -> None:
        self.operations = []
        self.sent = []

    def _record(self, action, details):
        self.operations.append({"action": action, "details": dict(details)})

    def last_draft(self):
        for item in reversed(self.operations):
            if item["action"] == "CREATE_DRAFT":
                return dict(item["details"])
        return {}

    def send_draft(self, draft_id):
        self.sent.append(draft_id)
        return {"message_id": "legacy-sent"}


class FakeProvider:
    def __init__(self) -> None:
        self.queries = []
        self.reply_drafts = []
        self.sent = []
        self.verify = True
        self.messages = [
            {
                "id": "m1",
                "thread_id": "t1",
                "from": "Anna <anna@example.com>",
                "to": "Kacper <k@example.com>",
                "subject": "Faktura lipiec",
                "date": "Fri, 31 Jul 2026 10:00:00 +0200",
                "snippet": "Czy możesz potwierdzić fakturę?",
            },
            {
                "id": "m2",
                "thread_id": "t2",
                "from": "Paweł <pawel@example.com>",
                "to": "Kacper <k@example.com>",
                "subject": "Raport",
                "date": "Fri, 31 Jul 2026 09:00:00 +0200",
                "snippet": "Raport jest gotowy.",
            },
        ]

    def list_gmail_messages(self, *, query, max_results):
        self.queries.append((query, max_results))
        return list(self.messages[:max_results])

    def get_gmail_message(self, message_id):
        base = next(item for item in self.messages if item["id"] == message_id)
        return {
            **base,
            "reply_to": "",
            "body": "Pełna treść wiadomości o fakturze.",
            "rfc_message_id": "<m1@example.com>",
            "references": "",
            "labels": ["INBOX"],
        }

    def get_gmail_thread(self, thread_id):
        return {
            "thread_id": thread_id,
            "count": 2,
            "messages": [
                {**self.get_gmail_message("m1"), "body": "Pierwsza wiadomość."},
                {
                    **self.get_gmail_message("m1"),
                    "id": "m3",
                    "from": "Kacper <k@example.com>",
                    "body": "Druga wiadomość.",
                },
            ],
        }

    def create_gmail_reply_draft(self, message_id, body):
        result = {
            "draft_id": "draft-reply-1",
            "message_id": "draft-message-1",
            "source_message_id": message_id,
            "thread_id": "t1",
            "recipient": "anna@example.com",
            "subject": "Re: Faktura lipiec",
        }
        self.reply_drafts.append((message_id, body, result))
        return result

    def send_gmail_draft_verified(self, draft_id):
        self.sent.append(draft_id)
        return {
            "message_id": "sent-1",
            "thread_id": "t1",
            "verified": self.verify,
            "labels": ["SENT"] if self.verify else [],
        }


class FakeOnline:
    def __init__(self, directory: str) -> None:
        self.project_root = Path(directory)
        self.provider = FakeProvider()
        self.gmail = FakeGmail()
        self.calendar = object()


class AssistantStub:
    def __init__(self, service):
        self.natural_actions = service


class B186B190GmailLiveWorkflowTests(unittest.TestCase):
    def service(self, directory: str, online: FakeOnline | None = None):
        return NaturalActionService(directory, online=online or FakeOnline(directory))

    def test_b186_live_search_is_read_only_and_uses_gmail_query(self) -> None:
        with TemporaryDirectory() as directory:
            online = FakeOnline(directory)
            service = self.service(directory, online)
            plan = service.plan("Znajdź maile od anna@example.com")
            response = service.handle("Znajdź maile od anna@example.com")
        self.assertEqual(plan["assistant_intent"], "gmail_search")
        self.assertTrue(plan["read_only"])
        self.assertFalse(plan["requires_confirmation"])
        self.assertIn("Anna", response)
        self.assertIn("from:anna@example.com", online.provider.queries[0][0])

    def test_b187_reads_full_message_and_thread_from_selected_result(self) -> None:
        with TemporaryDirectory() as directory:
            online = FakeOnline(directory)
            service = self.service(directory, online)
            service.handle("Pokaż najnowsze maile Gmail")
            message = service.handle("Przeczytaj pierwszy mail")
            thread = service.handle("Pokaż cały wątek")
        self.assertIn("Pełna treść", message)
        self.assertIn("Wątek ma 2 wiadomości", thread)
        self.assertIn("Druga wiadomość", thread)

    def test_b187_selected_message_survives_service_recreation(self) -> None:
        with TemporaryDirectory() as directory:
            online = FakeOnline(directory)
            service = self.service(directory, online)
            service.handle("Pokaż najnowsze maile Gmail")
            service.handle("Przeczytaj pierwszy mail")
            recreated = self.service(directory, online)
            response = recreated.handle("Pokaż cały wątek")
        self.assertIn("Wątek ma 2 wiadomości", response)

    def test_b188_reply_draft_requires_confirmation_and_does_not_send(self) -> None:
        with TemporaryDirectory() as directory:
            online = FakeOnline(directory)
            service = self.service(directory, online)
            service.handle("Pokaż najnowsze maile Gmail")
            service.handle("Przeczytaj pierwszy mail")
            plan = service.plan("Odpisz na ten mail, że faktura jest potwierdzona")
            response = PlannedNaturalActionExecutor.execute(AssistantStub(service), plan)
        self.assertEqual(plan["assistant_intent"], "gmail_reply_draft")
        self.assertTrue(plan["requires_confirmation"])
        self.assertIn("Faktura lipiec", plan["confirmation_message"])
        self.assertIn("nie została wysłana", response)
        self.assertEqual(len(online.provider.reply_drafts), 1)
        self.assertEqual(online.provider.sent, [])

    def test_b189_existing_reply_draft_sends_once_after_exact_confirmation(self) -> None:
        with TemporaryDirectory() as directory:
            online = FakeOnline(directory)
            service = self.service(directory, online)
            service.handle("Pokaż najnowsze maile Gmail")
            service.handle("Przeczytaj pierwszy mail")
            reply = service.plan("Odpisz na ten mail, że faktura jest potwierdzona")
            PlannedNaturalActionExecutor.execute(AssistantStub(service), reply)
            send = service.plan("Wyślij ten szkic")
            response = PlannedNaturalActionExecutor.execute(AssistantStub(service), send)
        self.assertEqual(send["assistant_intent"], "mail_send_existing")
        self.assertTrue(send["requires_confirmation"])
        self.assertEqual(online.provider.sent, ["draft-reply-1"])
        self.assertIn("sprawdzony w Gmail", response)

    def test_b189_rejects_unverified_send_result(self) -> None:
        with TemporaryDirectory() as directory:
            online = FakeOnline(directory)
            service = self.service(directory, online)
            service.handle("Pokaż najnowsze maile Gmail")
            service.handle("Przeczytaj pierwszy mail")
            PlannedNaturalActionExecutor.execute(
                AssistantStub(service),
                service.plan("Odpisz na ten mail, że faktura jest potwierdzona"),
            )
            online.provider.verify = False
            send = service.plan("Wyślij ten szkic")
            with self.assertRaises(OnlineAssistantError):
                PlannedNaturalActionExecutor.execute(AssistantStub(service), send)

    def test_b190_gate_and_stage_status_are_complete(self) -> None:
        with TemporaryDirectory() as directory:
            status = self.service(directory).status()
        stages = status["stages"]
        self.assertTrue(all(stage in stages for stage in (
            "B186", "B187", "B188", "B189", "B190"
        )))
        gate = GmailReliabilityGate.evaluate(status["gmail_live"])
        self.assertEqual(gate["status"], "B186_B190_GMAIL_LIVE_READY")
        self.assertEqual(gate["passed"], gate["total"])

    def test_b190_source_bounds_and_no_fixed_project_path(self) -> None:
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/natural_actions/service.py": 320,
            "app/natural_actions/runtime.py": 140,
            "app/natural_actions/understanding.py": 300,
            "app/online_assistant/google_workspace.py": 480,
            "app/natural_actions/gmail_live_actions.py": 180,
            "app/online_assistant/gmail_live_center.py": 190,
            "app/online_assistant/google_workspace_gmail_live.py": 230,
        }
        for relative, limit in limits.items():
            source = (root / relative).read_text(encoding="utf-8")
            self.assertLess(len(source.splitlines()), limit, relative)
            self.assertNotIn("C:/JarvisAI", source.replace("\\", "/"))


class _Operation:
    def __init__(self, value):
        self.value = value

    def execute(self):
        return self.value


class _Messages:
    def __init__(self, owner):
        self.owner = owner

    def get(self, **kwargs):
        message_id = kwargs["id"]
        if message_id == "sent-1":
            return _Operation({"id": "sent-1", "threadId": "t1", "labelIds": ["SENT"]})
        return _Operation(self.owner.message)


class _Threads:
    def __init__(self, owner):
        self.owner = owner

    def get(self, **_kwargs):
        return _Operation({"id": "t1", "messages": [self.owner.message]})


class _Drafts:
    def __init__(self, owner):
        self.owner = owner

    def create(self, **kwargs):
        self.owner.created_body = kwargs["body"]
        return _Operation({"id": "draft-1", "message": {"id": "dm1"}})


class _Users:
    def __init__(self, owner):
        self.owner = owner

    def messages(self):
        return _Messages(self.owner)

    def threads(self):
        return _Threads(self.owner)

    def drafts(self):
        return _Drafts(self.owner)


class _GmailService:
    def __init__(self, owner):
        self.owner = owner

    def users(self):
        return _Users(self.owner)


class ProviderHarness(GmailLiveProviderMixin):
    def __init__(self) -> None:
        encoded = base64.urlsafe_b64encode("Pełne ciało".encode()).decode().rstrip("=")
        self.message = {
            "id": "m1",
            "threadId": "t1",
            "labelIds": ["INBOX"],
            "snippet": "skrót",
            "payload": {
                "mimeType": "multipart/alternative",
                "headers": [
                    {"name": "From", "value": "Anna <anna@example.com>"},
                    {"name": "To", "value": "Kacper <k@example.com>"},
                    {"name": "Subject", "value": "Faktura"},
                    {"name": "Message-ID", "value": "<m1@example.com>"},
                ],
                "parts": [{"mimeType": "text/plain", "body": {"data": encoded}}],
            },
        }
        self.created_body = {}

    def _service(self, *_args):
        return _GmailService(self)

    def send_gmail_draft(self, draft_id):
        return {"message_id": "sent-1", "thread_id": "t1", "draft_id": draft_id}


class GmailLiveProviderTests(unittest.TestCase):
    def test_full_body_threaded_reply_and_sent_verification(self) -> None:
        provider = ProviderHarness()
        message = provider.get_gmail_message("m1")
        thread = provider.get_gmail_thread("t1")
        draft = provider.create_gmail_reply_draft("m1", "Potwierdzam")
        sent = provider.send_gmail_draft_verified("draft-1")
        raw = base64.urlsafe_b64decode(
            provider.created_body["message"]["raw"] + "=" * 3
        )
        parsed = message_from_bytes(raw)
        self.assertEqual(message["body"], "Pełne ciało")
        self.assertEqual(thread["count"], 1)
        self.assertEqual(provider.created_body["message"]["threadId"], "t1")
        self.assertEqual(parsed["In-Reply-To"], "<m1@example.com>")
        self.assertEqual(draft["recipient"], "anna@example.com")
        self.assertTrue(sent["verified"])


if __name__ == "__main__":
    unittest.main()
