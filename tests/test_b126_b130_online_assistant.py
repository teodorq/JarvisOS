from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from app.online_assistant.controller import OnlineAssistantController


class FakeReminderCenter:
    def status(self):
        return {
            "status": "REMINDER_CENTER_2_READY",
            "pending_count": 2,
            "next_reminder": {"text": "Sprawdzić raport", "due_at": "2026-07-20T09:00:00+00:00"},
        }


class FakeGoogleProvider:
    def __init__(self, *, connected: bool = True) -> None:
        self.connected = connected
        self.calls: list[tuple[str, object]] = []

    def dependency_status(self):
        return {"ready": True, "missing": [], "requirements_file": "requirements_google_workspace.txt"}

    def connection_status(self):
        return {
            "status": "GOOGLE_WORKSPACE_CONNECTED" if self.connected else "GOOGLE_WORKSPACE_NOT_CONNECTED",
            "dependency_ready": True,
            "missing_dependencies": [],
            "client_configured": True,
            "token_present": self.connected,
            "client_config_path": "C:/JarvisAI/config/google_workspace_client_secret.json",
            "token_path": "C:/JarvisAI/data/online_assistant/google_workspace_token.json",
            "scopes": [],
            "automatic_sending": False,
            "automatic_sync": False,
        }

    def connect(self):
        self.connected = True
        return {"status": "GOOGLE_WORKSPACE_CONNECTED", "gmail": True, "calendar": True, "drive": True}

    def disconnect(self):
        was_connected = self.connected
        self.connected = False
        return {"status": "GOOGLE_WORKSPACE_DISCONNECTED", "token_removed": was_connected}

    def live_probe(self):
        return {"gmail": self.connected, "calendar": self.connected, "drive": self.connected}

    def list_gmail_messages(self, *, query: str, max_results: int):
        self.calls.append(("gmail", query))
        return [
            {
                "id": "mail-1",
                "thread_id": "thread-1",
                "from": "Szef <boss@example.com>",
                "to": "kacper@example.com",
                "subject": "Raport dzienny",
                "date": "Sun, 19 Jul 2026 12:00:00 +0200",
                "snippet": "Proszę sprawdzić raport.",
                "unread": True,
                "important": True,
                "labels": ["INBOX", "UNREAD", "IMPORTANT"],
            }
        ][:max_results]

    def create_gmail_draft(self, recipient: str, subject: str, body: str):
        self.calls.append(("draft", recipient))
        return {
            "status": "GMAIL_DRAFT_CREATED",
            "draft_id": "draft-1",
            "message_id": "message-1",
            "recipient": recipient,
            "subject": subject,
        }

    def send_gmail_draft(self, draft_id: str):
        self.calls.append(("send", draft_id))
        return {"status": "GMAIL_DRAFT_SENT", "message_id": "message-sent", "thread_id": "thread-1"}

    def list_calendar_events(self, *, start_at: datetime, end_at: datetime, max_results: int = 25):
        self.calls.append(("calendar", start_at.isoformat()))
        start = datetime.now(timezone.utc) + timedelta(hours=1)
        return [
            {
                "id": "event-1",
                "title": "Spotkanie zespołu",
                "start_at": start.isoformat(),
                "end_at": (start + timedelta(minutes=30)).isoformat(),
                "location": "Online",
                "status": "confirmed",
                "html_link": "https://calendar.google.com/event",
            }
        ]

    def create_calendar_event(self, *, title: str, start_at: datetime, duration_minutes: int, description: str):
        self.calls.append(("create_event", title))
        return {
            "status": "GOOGLE_CALENDAR_EVENT_CREATED",
            "event_id": "event-new",
            "title": title,
            "start_at": start_at.isoformat(),
            "html_link": "https://calendar.google.com/event-new",
        }

    def search_drive_files(self, query: str, *, max_results: int):
        self.calls.append(("drive_search", query))
        return [
            {
                "id": "file-1",
                "name": "JARVIS raport.txt",
                "mime_type": "text/plain",
                "modified_at": "2026-07-19T12:00:00Z",
                "size": 50,
                "web_view_link": "https://drive.google.com/file-1",
            }
        ]

    def read_drive_text(self, file_id: str, mime_type: str):
        return "Pierwsze zdanie dokumentu jest ważne. Drugie zdanie opisuje plan pracy."

    def create_drive_text_file(self, name: str, content: str):
        self.calls.append(("drive_create", name))
        return {
            "status": "GOOGLE_DRIVE_FILE_CREATED",
            "file_id": "file-new",
            "name": name,
            "web_view_link": "https://drive.google.com/file-new",
        }


class OnlineAssistantControllerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.provider = FakeGoogleProvider()
        self.controller = OnlineAssistantController(
            self.root,
            provider=self.provider,
            reminders=FakeReminderCenter(),
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _mark_beta_ready(self) -> None:
        path = self.root / "data" / "assistant_v12" / "business_1_2_beta.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "version": "1.2",
                    "audits": [{"audit_id": "audit-beta", "status": "PASSED", "passed": 8, "total": 8}],
                    "confirmations": [{"status": "BUSINESS_1_2_BETA_READY"}],
                    "updated_at": "2026-07-19T00:00:00+00:00",
                }
            ),
            encoding="utf-8",
        )

    def test_matches_and_confirmation_policy(self) -> None:
        self.assertTrue(self.controller.matches("Pokaż najnowsze maile Gmail"))
        read_plan = self.controller.plan("Pokaż najnowsze maile Gmail")
        write_plan = self.controller.plan(
            "Utwórz szkic Gmail do test@example.com temat Test treść Wiadomość"
        )
        self.assertTrue(read_plan["read_only"])
        self.assertFalse(write_plan["read_only"])
        self.assertTrue(write_plan["requires_confirmation"])

    def test_live_read_flows(self) -> None:
        mail = self.controller.handle("Pokaż priorytetowe maile Gmail")
        calendar = self.controller.handle("Pokaż Kalendarz Google na dziś")
        drive = self.controller.handle("Wyszukaj na Dysku Google JARVIS")
        day = self.controller.handle("Pokaż centrum dnia online")
        self.assertIn("Raport dzienny", mail)
        self.assertIn("Spotkanie zespołu", calendar)
        self.assertIn("JARVIS raport.txt", drive)
        self.assertIn("CENTRUM DNIA ONLINE", day)

    def test_confirmed_write_flows(self) -> None:
        draft = self.controller.handle(
            "Utwórz szkic Gmail do test@example.com temat Test treść Treść wiadomości"
        )
        sent = self.controller.handle("Wyślij szkic Gmail draft-1")
        event = self.controller.handle(
            "Dodaj wydarzenie Google Spotkanie testowe na 2026-07-20 09:00 czas 45"
        )
        report = self.controller.handle("Zapisz raport na Dysku Google")
        self.assertIn("nie została wysłana", draft)
        self.assertIn("wysłany po potwierdzeniu", sent)
        self.assertIn("Spotkanie testowe", event)
        self.assertIn("raport zapisany", report)

    def test_drive_summary_is_bounded(self) -> None:
        response = self.controller.handle(
            "Podsumuj dokument z Dysku Google id file-1 typ text/plain nazwa Raport"
        )
        self.assertIn("Pierwsze zdanie", response)
        self.assertLess(len(response), 2200)

    def test_rc_audit_requires_existing_beta_and_live_connection(self) -> None:
        blocked = self.controller.run_rc_audit()
        self.assertEqual(blocked["status"], "BLOCKED")
        self._mark_beta_ready()
        passed = self.controller.run_rc_audit()
        self.assertEqual(passed["status"], "PASSED")
        self.assertEqual((passed["passed"], passed["total"]), (10, 10))
        confirmation = self.controller.confirm_rc()
        self.assertEqual(confirmation["status"], "BUSINESS_1_2_STABLE_RC_READY")
        self.assertTrue(self.controller.status()["rc"]["rc_ready"])

    def test_b130_gui_command_variants_route_to_rc_audit(self) -> None:
        from app.assistant.controller import PersonalAssistantController

        self._mark_beta_ready()
        assistant = PersonalAssistantController(self.root)
        assistant.online = self.controller

        for command in (
            "Uruchom audyt B130",
            "Uruchom test Business 1.2 Stable RC",
            "Uruchom audyt Business 1.2 Stable RC",
        ):
            with self.subTest(command=command):
                thought = assistant.plan(command)
                self.assertEqual(thought["handler"], "personal_assistant")
                self.assertEqual(thought["assistant_intent"], "rc_audit")
                response = assistant.handle(command)
                self.assertIn("audyt PASSED", response)
                self.assertIn("10/10", response)

    def test_status_never_contains_token_value(self) -> None:
        status_text = json.dumps(self.controller.status(), ensure_ascii=False)
        self.assertNotIn("refresh_token", status_text)
        self.assertNotIn("access_token", status_text)
        self.assertFalse(self.controller.status()["safety"]["automatic_sending"])

    def test_disconnect_requires_explicit_write_path(self) -> None:
        plan = self.controller.plan("Rozłącz Google Workspace")
        self.assertFalse(plan["read_only"])
        response = self.controller.handle("Rozłącz Google Workspace")
        self.assertIn("GOOGLE_WORKSPACE_DISCONNECTED", response)

    def test_real_provider_keeps_credentials_outside_project(self) -> None:
        from app.online_assistant.google_workspace import GoogleWorkspaceProvider

        provider = GoogleWorkspaceProvider(self.root)
        self.assertFalse(str(provider.token_path).startswith(str(self.root)))
        self.assertFalse(str(provider.client_config_path).startswith(str(self.root)))

    def test_changed_sources_stay_bounded(self) -> None:
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/assistant/controller.py": 480,
            "app/gui/main_window.py": 440,
            "app/gui/client_experience_window.py": 440,
            "app/online_assistant/controller.py": 500,
            "app/online_assistant/google_workspace.py": 480,
            "app/gui/online_assistant_page.py": 260,
        }
        for relative, limit in limits.items():
            with self.subTest(relative=relative):
                count = len((root / relative).read_text(encoding="utf-8").splitlines())
                self.assertLess(count, limit)


if __name__ == "__main__":
    unittest.main()
