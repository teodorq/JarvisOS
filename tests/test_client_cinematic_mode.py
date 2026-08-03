from __future__ import annotations

import os
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QMainWindow
from PySide6.QtTest import QTest

from app.gui.client_window_mode import ClientWindowModeRuntime
from app.gui.client_external_activity import (
    TODAY_CALENDAR_URL, open_external_companion, view_mode_for_thought,
)
from app.gui.halo_widget import HaloWidget
from app.gui.self_improvement_advisor import self_improvement_advice
from app.productivity.controller import ProductivitySuiteController


class _ClientWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.halo = HaloWidget()
        self.stable_label = QLabel("JARVIS ONLINE")
        self.fullscreen_calls = 0

    def showFullScreen(self) -> None:  # noqa: N802 - Qt API
        self.fullscreen_calls += 1
        super().showFullScreen()



class _ProjectIntelligence:
    def __init__(self) -> None:
        self.scan_calls = 0

    def scan_project(self) -> dict:
        self.scan_calls += 1
        return {"success": True, "scanned": 37, "opportunities": []}

    def select_best(self) -> dict:
        return {
            "selected": {
                "title": "Podziel zbyt duży moduł",
                "target": "app/ai/brain_response_formatter.py",
                "issue_type": "LARGE_MODULE",
                "confidence": 0.95,
                "risk_score": 42.0,
                "metadata": {"line_count": 2387},
            }
        }

class TestClientCinematicMode(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_polish_hud_has_no_broken_question_marks(self) -> None:
        source = Path("app/gui/client_hud_panels.py").read_text(encoding="utf-8")
        self.assertNotIn("??", source)
        self.assertIn("Pokaż mój plan na dziś", source)
        self.assertIn("Kliknij albo poproś własnymi słowami", source)

    def test_only_external_work_uses_pupil_until_manual_restore(self) -> None:
        window = _ClientWindow()
        runtime = ClientWindowModeRuntime(window)
        runtime.show_conversation()
        self.app.processEvents()
        self.assertEqual(window.fullscreen_calls, 1)

        runtime.update_state("thinking", 24)
        self.app.processEvents()
        self.assertTrue(window.isVisible())
        self.assertFalse(runtime.eye.isVisible())

        runtime.update_state("acting", 58, "pupil")
        self.app.processEvents()
        QTest.qWait(140)
        self.assertFalse(window.isVisible())
        self.assertTrue(runtime.eye.isVisible())
        self.assertEqual(runtime.eye.halo.state, "acting")

        runtime.update_state("success", 100)
        self.app.processEvents()
        self.assertFalse(window.isVisible())
        self.assertTrue(runtime.eye.isVisible())
        self.assertEqual(runtime.eye.halo.state, "success")

        runtime._restore_manually()
        self.app.processEvents()
        self.assertTrue(window.isVisible())
        self.assertFalse(runtime.eye.isVisible())
        self.assertEqual(window.fullscreen_calls, 1)
        self.assertEqual(window.stable_label.text(), "JARVIS DOSTĘPNY")
        runtime.close()
        window.close()

    def test_day_overview_opens_today_calendar_as_external_companion(self) -> None:
        opened: list[str] = []
        browser = SimpleNamespace(open_url=lambda url: opened.append(url) or "ok")
        window = SimpleNamespace(
            brain=SimpleNamespace(executor=SimpleNamespace(browser=browser))
        )
        thought = {"assistant_intent": "day_overview", "read_only": True}
        self.assertEqual(view_mode_for_thought(thought), "pupil")
        self.assertEqual(open_external_companion(window, thought), "ok")
        self.assertEqual(opened, [TODAY_CALENDAR_URL])
        self.assertEqual(
            view_mode_for_thought({"handler": "conversation"}),
            "conversation",
        )

    def test_self_improvement_question_uses_current_project_assessment(self) -> None:
        intelligence = _ProjectIntelligence()
        window = SimpleNamespace(
            brain=SimpleNamespace(project_intelligence_service=intelligence)
        )
        advice = self_improvement_advice(window, "Co byś w sobie zmienił?")
        self.assertIsNotNone(advice)
        self.assertEqual(intelligence.scan_calls, 1)
        self.assertIn("rzeczywisty stan", advice)
        self.assertIn("podziel zbyt duży moduł", advice)
        self.assertIn("2387 linii", advice)
        self.assertNotIn("przeglądarce", advice)
        self.assertNotIn("poczty sprzedażowej", advice)
        self.assertIsNone(self_improvement_advice(window, "Pokaż mój kalendarz"))

    def test_productivity_status_is_natural_polish(self) -> None:
        with TemporaryDirectory() as temporary:
            answer = ProductivitySuiteController(temporary).handle(
                "Status raportu produktywności"
            )
        self.assertIn("Raporty produktywności są gotowe", answer)
        self.assertIn("Plan zawiera", answer)
        self.assertNotIn("DAILY_PRODUCTIVITY", answer)
        self.assertNotIn("B110", answer)


if __name__ == "__main__":
    unittest.main()
