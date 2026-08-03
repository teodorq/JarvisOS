from __future__ import annotations

from tempfile import TemporaryDirectory
import unittest

from app.productivity.controller import ProductivitySuiteController
from app.assistant_v12.productivity_router import UnifiedProductivityRouter


class B1651ProactiveActionRoutingTests(unittest.TestCase):
    def test_natural_report_phrase_uses_friendly_review_intent(self):
        self.assertEqual(
            ProductivitySuiteController.intent("Sprawdź raport produktywności"),
            "report_review",
        )
        self.assertEqual(
            ProductivitySuiteController.intent("Przejrzyj raport produktywności"),
            "report_review",
        )
        self.assertEqual(
            ProductivitySuiteController.intent("Pokaż podsumowanie produktywności"),
            "report_review",
        )

    def test_report_review_is_read_only_and_client_safe(self):
        with TemporaryDirectory() as directory:
            controller = ProductivitySuiteController(directory)
            controller.reporting.snapshot = lambda: {
                "mail": {"ready_count": 1},
                "calendar": {"upcoming_count": 2},
                "reminders": {"due_count": 1},
            }
            plan = controller.plan("Sprawdź raport produktywności")
            response = controller.handle("Sprawdź raport produktywności")

        self.assertTrue(plan["read_only"])
        self.assertIn("Podsumowanie produktywności", response)
        self.assertIn("szkice do sprawdzenia: 1", response)
        self.assertIn("nadchodzące wydarzenia: 2", response)
        self.assertIn("pilne przypomnienia: 1", response)
        self.assertIn("Oznacz raport jako zrobione", response)
        for forbidden in ("B110", "READY", "C:\\", "/JarvisAI/", "text_path"):
            self.assertNotIn(forbidden, response)

    def test_owner_technical_status_command_remains_available(self):
        self.assertEqual(
            ProductivitySuiteController.intent("Status B110"),
            "report_status",
        )
        self.assertEqual(
            ProductivitySuiteController.intent("Status raportu produktywności"),
            "report_status",
        )

    def test_unified_router_returns_safe_report_summary(self):
        with TemporaryDirectory() as directory:
            router = UnifiedProductivityRouter(directory)
            router.productivity.reporting.snapshot = lambda: {
                "mail": {"ready_count": 0},
                "calendar": {"upcoming_count": 0},
                "reminders": {"due_count": 0},
            }
            response = router.execute("report_status", {})

        self.assertIn("Podsumowanie produktywności", response)
        self.assertNotIn("B110", response)
        self.assertNotIn("C:\\", response)

    def test_source_limits_and_no_hardcoded_project_path(self):
        from pathlib import Path

        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/productivity/controller.py": 340,
            "app/assistant_v12/productivity_router.py": 140,
        }
        for relative, limit in limits.items():
            source = (root / relative).read_text(encoding="utf-8")
            self.assertLess(len(source.splitlines()), limit, relative)
            self.assertNotIn("C:/JarvisAI", source.replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()
