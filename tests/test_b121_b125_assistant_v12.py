from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.assistant.controller import PersonalAssistantController
from app.assistant_v12.controller import AssistantV12Controller


class TestB121B125AssistantV12(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.controller = AssistantV12Controller(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_b121_calendar_follow_up_uses_context(self) -> None:
        first = self.controller.handle("Dodaj spotkanie Przegląd projektu")
        self.assertIn("Podaj termin", first)
        thought = self.controller.plan("jutro o 9")
        self.assertEqual(thought["assistant_intent"], "calendar_add")
        self.assertFalse(thought["read_only"])
        result = self.controller.handle("jutro o 9")
        self.assertIn("Przegląd projektu", result)
        self.assertEqual(
            self.controller.status()["context"]["last_intent"],
            "calendar_add",
        )

    def test_b121_mail_draft_requires_recipient_and_is_not_read_only(self) -> None:
        prompt = self.controller.handle("Napisz mail temat: Raport")
        self.assertIn("adres e-mail", prompt)
        thought = self.controller.plan("do kontakt@example.com")
        self.assertFalse(thought["read_only"])
        result = self.controller.handle("do kontakt@example.com")
        self.assertIn("Nic nie wysłałem", result)
        self.assertEqual(
            self.controller.router.productivity.mail.status()["draft_count"],
            1,
        )

    def test_b123_day_overview_is_read_only(self) -> None:
        thought = self.controller.plan("Pokaż mój dzień")
        self.assertTrue(thought["read_only"])
        result = self.controller.handle("Pokaż mój dzień")
        self.assertIn("Twój dzień", result)

    def test_b124_progress_is_durable(self) -> None:
        self.controller.handle("Pokaż mój dzień")
        status = self.controller.status()["progress"]
        self.assertEqual(status["completed_count"], 1)
        self.assertEqual(status["latest"]["status"], "COMPLETED")
        self.assertEqual(status["latest"]["progress_percent"], 100)

    def test_b125_audit_and_confirmation(self) -> None:
        with patch(
            "app.assistant_v12.controller.ClientExperienceController.status",
            return_value={"stable_ready": True},
        ):
            audit = self.controller.run_beta_audit()
            self.assertEqual(audit["status"], "PASSED")
            self.assertEqual(audit["passed"], 8)
            confirmation = self.controller.confirm_beta()
        self.assertEqual(confirmation["status"], "BUSINESS_1_2_BETA_READY")
        self.assertTrue(self.controller.status()["beta"]["beta_ready"])

    def test_personal_assistant_routes_v12_before_legacy_productivity(self) -> None:
        assistant = PersonalAssistantController(self.root)
        thought = assistant.plan("Pokaż mój dzień")
        self.assertEqual(thought["handler"], "personal_assistant")
        self.assertEqual(thought["assistant_intent"], "day_overview")
        result = assistant.handle("Pokaż mój dzień")
        self.assertIn("Twój dzień", result)

    def test_safe_defaults(self) -> None:
        safety = self.controller.status()["safety"]
        self.assertFalse(safety["auto_approve"])
        self.assertFalse(safety["remote_sync"])
        self.assertFalse(safety["automatic_sending"])
        self.assertEqual(safety["max_active_executions"], 1)


if __name__ == "__main__":
    unittest.main()
