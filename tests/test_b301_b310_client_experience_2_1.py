from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import os
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from app.assistant.controller import PersonalAssistantController
from app.assistant.voice_runtime import VoiceRuntimeService
from app.gui.client_capability_policy import ClientCapabilityPolicy
from app.jarvis_experience.isolation import ClientIsolationPolicy
from app.natural_actions.advanced_understanding import classify_advanced
from app.natural_actions.gmail_live_actions import GmailLiveNaturalActions
from app.productivity.controller import ProductivitySuiteController

try:
    from PySide6.QtWidgets import QMessageBox
    from app.gui.client_owner_access import ClientOwnerAccess
    HAS_QT = True
except ModuleNotFoundError:
    QMessageBox = None
    ClientOwnerAccess = None
    HAS_QT = False


class TestB301B310ClientExperience21(unittest.TestCase):
    def test_owner_commands_are_blocked_but_daily_work_remains_available(self) -> None:
        for command in (
            "Uruchom AutoDev",
            "Wdróż przygotowaną poprawkę",
            "Eksportuj raport audytu",
            "Ustaw rolę owner",
            "Pokaż licencję",
        ):
            with self.subTest(command=command):
                self.assertIn(
                    "tylko w trybie właściciela",
                    ClientCapabilityPolicy.denial_message(command),
                )
        for command in (
            "Pokaż mój plan na dziś",
            "Znajdź najnowsze wiadomości Gmail",
            "Pokaż najbliższe przypomnienia",
        ):
            with self.subTest(command=command):
                self.assertEqual(ClientCapabilityPolicy.denial_message(command), "")

    def test_planned_owner_handlers_are_blocked(self) -> None:
        for handler in (
            "autonomous_autodev",
            "software_engineer",
            "business_audit",
            "release_deployment",
        ):
            with self.subTest(handler=handler):
                self.assertIn(
                    "tylko w trybie właściciela",
                    ClientCapabilityPolicy.denial_for_thought(
                        {"handler": handler}
                    ),
                )
        self.assertEqual(
            ClientCapabilityPolicy.denial_for_thought(
                {"handler": "natural_action", "intent": "day_overview"}
            ),
            "",
        )

    @unittest.skipUnless(HAS_QT, "PySide6 is unavailable")
    def test_client_cannot_enrol_owner_pin(self) -> None:
        unlocked: list[bool] = []
        access = ClientOwnerAccess.__new__(ClientOwnerAccess)
        access.parent = None
        access.gate = SimpleNamespace(has_pin=lambda: False)
        access.on_unlocked = lambda: unlocked.append(True)
        with patch.object(QMessageBox, "warning") as warning:
            access.request_unlock()
        self.assertEqual(unlocked, [])
        warning.assert_called_once()
        self.assertFalse(hasattr(ClientOwnerAccess, "_create_pin"))

    def test_status_answers_hide_internal_stage_codes(self) -> None:
        with TemporaryDirectory() as temporary:
            assistant = PersonalAssistantController(temporary)
            conversation = assistant.handle("Status rozmowy")
            desktop = assistant.handle("Status sterowania pulpitem")
            daily = assistant.handle("Status codziennej pracy")
        self.assertIn("Pamiętam", conversation)
        self.assertNotIn("B96", conversation)
        self.assertNotIn("Ostatnia intencja", conversation)
        self.assertIn("Sterowanie pulpitem działa", desktop)
        self.assertNotIn("RELIABLE DESKTOP", desktop)
        self.assertNotIn("Faza:", daily)
        self.assertNotIn("B100", daily)

    def test_natural_reminder_query_is_routed_and_explained(self) -> None:
        with TemporaryDirectory() as temporary:
            productivity = ProductivitySuiteController(temporary)
            productivity.reminders.add(
                "Sprawdź ofertę",
                due_at=datetime.now(timezone.utc) + timedelta(minutes=30),
            )
            answer = productivity.handle("Pokaż najbliższe przypomnienia")
        self.assertTrue(
            ProductivitySuiteController.matches("Pokaż najbliższe przypomnienia")
        )
        self.assertIn("Najbliższe", answer)
        self.assertIn("Sprawdź ofertę", answer)
        self.assertNotIn("B109", answer)

    def test_plan_for_today_is_a_natural_day_overview(self) -> None:
        self.assertEqual(
            classify_advanced("Pokaż mój plan na dziś")[0],
            "day_overview",
        )

    def test_gmail_search_is_numbered_and_keeps_line_breaks(self) -> None:
        action = GmailLiveNaturalActions.__new__(GmailLiveNaturalActions)
        action.center = SimpleNamespace(search=lambda _query, _limit: [
            {
                "from": 'Biuro Obsługi <kontakt@example.com>',
                "subject": "Potwierdzenie spotkania",
            },
            {"from": "alert@example.com", "subject": "Nowe logowanie"},
        ])
        request = SimpleNamespace(intent="gmail_search", slots={"query": "in:inbox"})
        answer = action.execute(request)
        self.assertIn("1. Biuro Obsługi (kontakt@example.com)", answer)
        self.assertIn("\n2. alert@example.com", answer)
        self.assertIn("Przeczytaj wiadomość numer 1", answer)
        self.assertNotIn("Wybrałem pierwszą", answer)
        self.assertIn("\n", ClientIsolationPolicy.sanitize_action_result(answer))

    def test_voice_defaults_use_the_calm_cinematic_profile(self) -> None:
        with TemporaryDirectory() as temporary:
            settings = VoiceRuntimeService(temporary).settings()
        self.assertEqual(settings["voice_profile"], "CALM_CINEMATIC")
        self.assertEqual(settings["preferred_gender"], "Male")
        self.assertLess(settings["speech_rate"], 175)
        self.assertLessEqual(settings["volume"], 1.0)
        self.assertLess(settings["pitch"], 1.0)

    def test_hud_source_and_file_limits_remain_bounded(self) -> None:
        root = Path(__file__).resolve().parents[1]
        client = (root / "app/gui/client_experience_window.py").read_text(
            encoding="utf-8"
        )
        theme = (root / "app/gui/client_theme.py").read_text(encoding="utf-8")
        backdrop = (root / "app/gui/client_hud_backdrop.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("ClientHudBackdrop", client)
        self.assertIn("PRZYPOMNIENIA", client)
        self.assertIn("rgba(2, 10, 19, 174)", theme)
        self.assertIn("spacing = 42", backdrop)
        self.assertLess(len(client.splitlines()), 440)
        self.assertLess(len(theme.splitlines()), 120)


if __name__ == "__main__":
    unittest.main()
