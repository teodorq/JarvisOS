from __future__ import annotations

from datetime import datetime
import os
from types import SimpleNamespace
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QLineEdit, QPushButton, QVBoxLayout, QWidget

from app.assistant.controller import PersonalAssistantController
from app.assistant.natural_language import NaturalLanguageService
from app.gui.client_capability_policy import ClientCapabilityPolicy
from app.gui.client_exit_intent import is_jarvis_exit_request
from app.gui.client_external_activity import (
    WEEK_CALENDAR_URL, open_external_companion, view_mode_for_thought,
)
from app.gui.client_hud_panels import build_client_hud_row
from app.gui.client_tool_drawer import ClientToolDrawer, SAFE_CLIENT_ACTIONS
from app.natural_actions.business_day_intelligence import BusinessDayIntelligenceService
from app.natural_actions.business_day_understanding import classify_business_day
from app.natural_actions.understanding import NaturalActionUnderstanding
from app.productivity.controller import ProductivitySuiteController


class _DrawerWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        layout = QVBoxLayout(self)
        self.message_label = QLabel("Gotowy")
        self.activity_label = QLabel("Gotowy")
        self.command_entry = QLineEdit()
        self.tools_button = QPushButton("WIĘCEJ")
        self.submitted: list[str] = []
        layout.addWidget(self.message_label)
        layout.addWidget(self.activity_label)
        layout.addWidget(self.command_entry)

    def _submit_text(self, text: str) -> None:
        self.submitted.append(text)


class _HudWindow(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.experience_v2 = SimpleNamespace(toggle_tools=lambda: None)
        self.commands: list[str] = []

    def _submit_text(self, text: str) -> None:
        self.commands.append(text)


class _Daily:
    @staticmethod
    def _priority(_snapshot):
        return ""

    @staticmethod
    def _moment(_value):
        return ""


class ClientProductFunctionAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    @classmethod
    def tearDownClass(cls) -> None:
        app = QApplication.instance()
        if app is not None:
            app.quit()

    def test_every_direct_client_action_has_a_real_intent(self):
        for _group, actions in SAFE_CLIENT_ACTIONS:
            for action in actions:
                with self.subTest(action=action.label):
                    self.assertEqual(ClientCapabilityPolicy.denial_message(action.command), "")
                    if not action.guided:
                        intent, confidence = NaturalActionUnderstanding.classify(action.command)
                        core_intent = NaturalLanguageService.classify(action.command)
                        self.assertTrue(
                            intent != "standard" or core_intent != "standard",
                            f"Brak routingu dla działania: {action.label}",
                        )
                        if intent != "standard":
                            self.assertGreaterEqual(confidence, 0.7)

    def test_owner_financial_tools_are_absent_and_blocked_in_client(self):
        labels = {action.label for _group, actions in SAFE_CLIENT_ACTIONS for action in actions}
        self.assertNotIn("REKLAMY", labels)
        self.assertNotIn("TRADING", labels)
        for command in (
            "Ile wydaliśmy na reklamy?",
            "Jaki był wynik tradingu?",
            "Podsumuj biznes",
        ):
            with self.subTest(command=command):
                self.assertIn("tylko w trybie właściciela", ClientCapabilityPolicy.denial_message(command))
        for intent in ("advertising_overview", "trading_overview", "day_business_summary"):
            with self.subTest(intent=intent):
                denial = ClientCapabilityPolicy.denial_for_thought({"assistant_intent": intent})
                self.assertIn("tylko w trybie właściciela", denial)

    def test_day_review_stays_in_conversation_and_opens_no_gmail(self):
        opened: list[str] = []
        window = SimpleNamespace(
            brain=SimpleNamespace(executor=SimpleNamespace(
                browser=SimpleNamespace(open_url=lambda url: opened.append(url))
            ))
        )
        thought = {"assistant_intent": "day_review", "read_only": True}
        self.assertEqual(view_mode_for_thought(thought), "conversation")
        self.assertEqual(open_external_companion(window, thought), "")
        self.assertEqual(opened, [])

    def test_calendar_week_uses_a_real_week_range_and_week_view(self):
        self.assertEqual(
            classify_business_day("Pokaż mój kalendarz na ten tydzień")[0],
            "calendar_week_overview",
        )
        opened: list[str] = []
        window = SimpleNamespace(
            brain=SimpleNamespace(executor=SimpleNamespace(
                browser=SimpleNamespace(open_url=lambda url: opened.append(url) or url)
            ))
        )
        thought = {"assistant_intent": "calendar_week_overview", "read_only": True}
        self.assertEqual(view_mode_for_thought(thought), "pupil")
        self.assertEqual(open_external_companion(window, thought), WEEK_CALENDAR_URL)
        self.assertEqual(opened, [WEEK_CALENDAR_URL])
        calls: list[tuple[str, dict]] = []

        class Calendar:
            def find_events(self, query, **kwargs):
                calls.append((query, kwargs))
                return []

        service = object.__new__(BusinessDayIntelligenceService)
        service.online = SimpleNamespace(calendar=Calendar())
        self.assertEqual(service._week_events(), [])
        self.assertEqual(calls[0][0], "")
        self.assertLess(calls[0][1]["start_at"], calls[0][1]["end_at"])
        self.assertEqual(calls[0][1]["max_results"], 50)

    def test_client_day_has_no_owner_metrics_but_owner_summary_keeps_them(self):
        service = object.__new__(BusinessDayIntelligenceService)
        service.daily = _Daily()
        data = {
            "available": {"events": True, "mail": True},
            "events": [], "mail": [], "drive_documents": [], "local_documents": [],
            "reminders": {"pending_count": 0, "due_count": 0},
            "mail_activity": {},
            "mail_insights": {"bills": [], "advertising": [], "bill_totals": {}, "advertising_totals": {}},
            "metrics": {
                "sales": {"connected": True, "record_count": 1, "totals": {"PLN": 10}},
                "advertising": {"connected": True, "record_count": 1, "totals": {"PLN": 5}},
                "trading": {"connected": True, "record_count": 1, "totals": {"PLN": 3}},
            },
            "completed": [], "actions": [], "now": datetime.now().astimezone(),
        }
        client = service._full_day(data, business=False, review=True)
        owner = service._full_day(data, business=True)
        for marker in ("Reklamy:", "Trading:", "Sprzedaż:"):
            self.assertNotIn(marker, client)
            self.assertIn(marker, owner)

    def test_guided_actions_close_drawer_and_show_what_to_do(self):
        window = _DrawerWindow()
        drawer = ClientToolDrawer(window)
        guided = next(
            action for _group, actions in SAFE_CLIENT_ACTIONS
            for action in actions if action.guided
        )
        window.show()
        drawer.show()
        drawer.run(guided)
        self.assertFalse(drawer.isVisible())
        self.assertEqual(window.command_entry.text(), guided.command)
        self.assertIn("naciśnij Enter", window.activity_label.text())
        window.close()

    def test_completed_guided_commands_reach_existing_services(self):
        reminder = "Przypomnij mi o rachunku jutro o 18"
        self.assertIsNone(classify_business_day(reminder))
        self.assertTrue(PersonalAssistantController.matches(reminder))
        self.assertTrue(ProductivitySuiteController.matches("Znajdź dokument umowa"))
        self.assertEqual(
            NaturalActionUnderstanding.classify("Dodaj do kalendarza spotkanie jutro o 12")[0],
            "calendar_create",
        )

    def test_natural_exit_understands_variants_but_not_other_apps(self):
        for command in (
            "Jarvis, koniec na dziś",
            "Jarvis zamknij swój program",
            "Możesz się wyłączyć",
            "Wyłącz program Jarvis",
            "Do jutra Jarvis",
        ):
            with self.subTest(command=command):
                self.assertTrue(is_jarvis_exit_request(command))
        for command in (
            "Jarvis zamknij przeglądarkę",
            "Zamknij dokument",
            "Wyłącz kalkulator",
            "Koniec spotkania o 18",
        ):
            with self.subTest(command=command):
                self.assertFalse(is_jarvis_exit_request(command))

    def test_client_hud_has_a_visible_exit_button(self):
        window = _HudWindow()
        layout = build_client_hud_row(window, QLabel("JARVIS"))
        self.assertIsNotNone(layout)
        self.assertEqual(window.exit_button.text(), "WYJDŹ")
        window.close()


if __name__ == "__main__":
    unittest.main()
