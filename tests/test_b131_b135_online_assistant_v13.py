from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import tempfile
import unittest

from app.online_assistant.controller import OnlineAssistantController
from app.online_assistant_v13.controller import OnlineAssistantV13Controller
from app.online_assistant_v13.reliability import WorkspaceReliabilityService


class PreviousReady:
    def status(self):
        return {
            "connection": {
                "dependency_ready": True,
                "client_configured": True,
                "token_present": True,
                "token_path": "C:/Users/Test/AppData/Local/JARVIS_OS/secrets/google_workspace_token.json",
            },
            "rc": {"rc_ready": True},
        }


class FakeProviderV13:
    def __init__(self) -> None:
        self.connected = True
        self.calls: list[tuple[str, object]] = []
        self.probe_failures = 0
        self.read_failures = 0

    def connection_status(self):
        return {
            "status": "GOOGLE_WORKSPACE_CONNECTED",
            "dependency_ready": True,
            "missing_dependencies": [],
            "client_configured": True,
            "token_present": self.connected,
            "client_config_path": "C:/Users/Test/AppData/Local/JARVIS_OS/secrets/client.json",
            "token_path": "C:/Users/Test/AppData/Local/JARVIS_OS/secrets/token.json",
            "automatic_sending": False,
            "automatic_sync": False,
        }

    def live_probe(self):
        if self.probe_failures:
            self.probe_failures -= 1
            raise RuntimeError("503 service unavailable")
        return {"gmail": self.connected, "calendar": self.connected, "drive": self.connected}

    def list_gmail_messages(self, *, query: str, max_results: int):
        self.calls.append(("gmail", query))
        if self.read_failures:
            self.read_failures -= 1
            raise RuntimeError("503 service unavailable")
        return [
            {
                "id": "mail-urgent", "from": "Szef <boss@example.com>",
                "subject": "Pilne: faktura i termin", "snippet": "Proszę dziś.",
                "date": "2026-07-19", "unread": True, "important": True,
                "labels": ["INBOX", "UNREAD", "IMPORTANT"],
            },
            {
                "id": "mail-normal", "from": "Team <team@example.com>",
                "subject": "Aktualizacja", "snippet": "Informacja tygodniowa.",
                "date": "2026-07-18", "unread": False, "important": False,
                "labels": ["INBOX"],
            },
        ][:max_results]

    def create_gmail_draft(self, recipient: str, subject: str, body: str):
        self.calls.append(("draft", recipient))
        return {"status": "GMAIL_DRAFT_CREATED", "draft_id": "draft-v13", "message_id": "m1", "recipient": recipient, "subject": subject}

    def send_gmail_draft(self, draft_id: str):
        self.calls.append(("send", draft_id))
        return {"status": "GMAIL_DRAFT_SENT", "message_id": "sent-v13", "thread_id": "t1"}

    def archive_gmail_message(self, message_id: str):
        self.calls.append(("archive", message_id))
        return {"status": "GMAIL_MESSAGE_ARCHIVED", "message_id": message_id, "labels": []}

    def add_gmail_label(self, message_id: str, label_name: str):
        self.calls.append(("label", label_name))
        return {"status": "GMAIL_LABEL_ADDED", "message_id": message_id, "label": label_name}

    def list_calendar_events(self, *, start_at: datetime, end_at: datetime, max_results: int = 25):
        self.calls.append(("calendar", start_at.isoformat()))
        base = datetime.now(timezone.utc) + timedelta(hours=2)
        return [
            {"id": "e1", "title": "Spotkanie A", "start_at": base.isoformat(), "end_at": (base + timedelta(hours=1)).isoformat()},
            {"id": "e2", "title": "Spotkanie B", "start_at": (base + timedelta(minutes=30)).isoformat(), "end_at": (base + timedelta(hours=2)).isoformat()},
        ]

    def create_calendar_event(self, *, title: str, start_at: datetime, duration_minutes: int, description: str):
        self.calls.append(("create_event", title))
        return {"status": "GOOGLE_CALENDAR_EVENT_CREATED", "event_id": "event-v13", "title": title, "start_at": start_at.isoformat()}

    def search_drive_files(self, query: str, *, max_results: int):
        self.calls.append(("drive_search", query))
        return [{"id": "file-1", "name": "Plan JARVIS.txt", "mime_type": "text/plain", "modified_at": "2026-07-19", "size": 80}]

    def read_drive_text(self, file_id: str, mime_type: str):
        return "Pierwsze ważne zdanie dokumentu. Drugie zdanie opisuje plan tygodnia i kolejne zadania."

    def create_drive_text_file(self, name: str, content: str):
        self.calls.append(("drive_create", name))
        return {"status": "GOOGLE_DRIVE_FILE_CREATED", "file_id": f"file-{len(self.calls)}", "name": name, "web_view_link": "https://drive.test/file"}


class OnlineAssistantV13Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.provider = FakeProviderV13()
        self.controller = OnlineAssistantV13Controller(
            self.root,
            provider=self.provider,
            previous=PreviousReady(),
            sleep=lambda _seconds: None,
        )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_b131_b135_matches_and_confirmation_policy(self) -> None:
        self.assertTrue(self.controller.matches("Pokaż skrzynkę pracy Gmail"))
        self.assertTrue(self.controller.matches("Uruchom audyt B135"))
        read = self.controller.plan("Zaproponuj terminy Google czas 30")
        write = self.controller.plan("Archiwizuj Gmail mail-1")
        self.assertTrue(read["read_only"])
        self.assertFalse(write["read_only"])
        self.assertTrue(write["requires_confirmation"])

    def test_b131_retries_safe_reads_and_uses_cache_offline(self) -> None:
        first = self.controller.gmail.briefing()
        self.assertEqual(first["mode"], "LIVE")
        self.provider.read_failures = 3
        cached = self.controller.gmail.briefing()
        self.assertEqual(cached["mode"], "CACHED_OFFLINE")
        self.assertTrue(self.controller.reliability.status()["offline_mode"])
        self.assertLessEqual(self.controller.reliability.status()["max_read_attempts"], 3)

    def test_b131_probe_retries_then_passes(self) -> None:
        self.provider.probe_failures = 2
        probe = self.controller.reliability.probe()
        self.assertEqual(probe["status"], "HEALTHY")
        self.assertEqual(probe["mode"], "LIVE")

    def test_b132_gmail_workflows(self) -> None:
        briefing = self.controller.gmail.briefing()
        self.assertEqual(briefing["messages"][0]["id"], "mail-urgent")
        self.assertGreater(briefing["messages"][0]["priority_score"], briefing["messages"][1]["priority_score"])
        self.assertIn("szkic", self.controller.handle("Utwórz szkic Gmail 1.3 do test@example.com temat Test treść Treść").casefold())
        self.assertIn("wysłany", self.controller.handle("Wyślij szkic Gmail 1.3 draft-v13"))
        self.assertIn("zarchiwizowana", self.controller.handle("Archiwizuj Gmail mail-urgent"))
        self.assertIn("VIP", self.controller.handle("Dodaj etykietę Gmail mail-urgent nazwa VIP"))

    def test_b133_calendar_intelligence(self) -> None:
        week = self.controller.calendar.week()
        slots = self.controller.calendar.suggest_slots(duration_minutes=30)
        self.assertEqual(week["conflict_count"], 1)
        self.assertLessEqual(len(slots["slots"]), 5)
        response = self.controller.handle("Pokaż plan tygodnia Google")
        self.assertIn("konflikty 1", response)

    def test_b134_drive_documents_and_versions(self) -> None:
        summary = self.controller.handle("Podsumuj dokument online id file-1 typ text/plain nazwa Plan")
        self.assertIn("Pierwsze ważne zdanie", summary)
        first = self.controller.handle("Utwórz dokument online 1.3 nazwa Raport treść Pierwsza wersja")
        second = self.controller.handle("Utwórz dokument online 1.3 nazwa Raport treść Druga wersja")
        self.assertIn("wersję 1", first)
        self.assertIn("wersję 2", second)
        self.assertEqual(len(self.controller.drive.versions("Raport")), 2)

    def test_b135_audit_and_confirmation(self) -> None:
        audit = self.controller.run_beta_audit()
        self.assertEqual(audit["status"], "PASSED")
        self.assertEqual((audit["passed"], audit["total"]), (12, 12))
        confirmation = self.controller.confirm_beta()
        self.assertEqual(confirmation["status"], "ONLINE_ASSISTANT_1_3_BETA_READY")
        self.assertTrue(self.controller.status()["beta"]["beta_ready"])

    def test_b135_blocks_without_b130_rc(self) -> None:
        class PreviousBlocked:
            def status(self):
                value = PreviousReady().status()
                value["rc"]["rc_ready"] = False
                return value

        controller = OnlineAssistantV13Controller(
            self.root, provider=self.provider, previous=PreviousBlocked(), sleep=lambda _seconds: None
        )
        audit = controller.run_beta_audit()
        self.assertEqual(audit["status"], "BLOCKED")
        with self.assertRaises(ValueError):
            controller.confirm_beta()

    def test_existing_online_controller_routes_b135_commands(self) -> None:
        online = OnlineAssistantController(self.root, provider=self.provider)
        online.v13.previous = PreviousReady()
        plan = online.plan("Uruchom audyt B135")
        self.assertEqual(plan["assistant_intent"], "beta_audit")
        response = online.handle("Uruchom audyt B135")
        self.assertIn("PASSED", response)
        self.assertIn("12/12", response)

    def test_personal_assistant_gui_command_routing(self) -> None:
        from app.assistant.controller import PersonalAssistantController

        assistant = PersonalAssistantController(self.root)
        assistant.online = OnlineAssistantController(self.root, provider=self.provider)
        assistant.online.v13.previous = PreviousReady()
        thought = assistant.plan("Uruchom audyt B135")
        self.assertEqual(thought["handler"], "personal_assistant")
        self.assertEqual(thought["assistant_intent"], "beta_audit")
        response = assistant.handle("Uruchom audyt B135")
        self.assertIn("12/12", response)

    def test_status_never_exposes_tokens_or_enables_auto_send(self) -> None:
        serialized = json.dumps(self.controller.status(), ensure_ascii=False)
        self.assertNotIn("refresh_token", serialized)
        self.assertNotIn("access_token", serialized)
        self.assertFalse(self.controller.status()["safety"]["automatic_sending"])
        self.assertFalse(self.controller.status()["safety"]["auto_approve"])

    def test_changed_sources_stay_bounded(self) -> None:
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/assistant/controller.py": 480,
            "app/gui/main_window.py": 440,
            "app/online_assistant/controller.py": 500,
            "app/online_assistant/google_workspace.py": 480,
            "app/gui/online_assistant_page.py": 260,
            "app/online_assistant_v13/controller.py": 480,
            "app/online_assistant_v13/reliability.py": 220,
            "app/gui/online_assistant_v13_panel.py": 140,
        }
        for relative, limit in limits.items():
            with self.subTest(relative=relative):
                count = len((root / relative).read_text(encoding="utf-8").splitlines())
                self.assertLess(count, limit)


if __name__ == "__main__":
    unittest.main()
