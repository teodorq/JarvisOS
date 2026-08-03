from __future__ import annotations

import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication, QLabel, QPushButton, QVBoxLayout, QWidget

from app.core.user_text import contains_stage_code, naturalize_user_text
from app.gui.business_pages import ConsolePage
from app.gui.business_status_snapshot import business_service_snapshot
from app.gui.user_text_widgets import clean_user_visible_widgets
from app.jarvis_experience.isolation import ClientIsolationPolicy
from app.voice.speech_director import PolishSpeechDirector


class TestB371B380LanguageStability(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])

    def test_manifest_closes_all_internal_milestones(self) -> None:
        manifest = json.loads(
            Path("config/b371_b380_language_stability.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(
            list(manifest["stages"]),
            [f"B{number}" for number in range(371, 381)],
        )
        self.assertFalse(manifest["rules"]["stage_ids_visible_to_user"])
        self.assertEqual(manifest["rules"]["owner_command_workers"], 1)

    def test_shared_filter_removes_codes_from_any_position(self) -> None:
        text = naturalize_user_text(
            "Asystent B96–B100: GOTOWY. B100 Faza: COMPLETED."
        )
        self.assertFalse(contains_stage_code(text))
        self.assertNotIn("COMPLETED", text)
        self.assertIn("zakończone", text)
        self.assertEqual(naturalize_user_text("sprzedaż B2B"), "sprzedaż B2B")
        self.assertEqual(naturalize_user_text("samolot B737"), "samolot B737")
        self.assertEqual(
            naturalize_user_text("Kalendarz: „Spotkanie B174”"),
            "Kalendarz: „Spotkanie B174”",
        )

    def test_machine_status_becomes_a_readable_sentence_fragment(self) -> None:
        text = naturalize_user_text(
            "B110 DAILY_PRODUCTIVITY_SUITE_READY"
        )
        self.assertEqual(text, "narzędzia codziennej pracy są gotowe")
        self.assertNotIn("_", text)

    def test_console_filters_dynamic_responses_and_states(self) -> None:
        console = ConsolePage()
        console.append("Jarvis: B125 ASSISTANT_1_2_SUITE_READY")
        console.set_state("B125: READY", "healthy")
        self.assertNotIn("B125", console.chat.toPlainText())
        self.assertIn("asystent jest gotowy", console.chat.toPlainText())
        self.assertNotIn("B125", console.state_pill.full_text)

    def test_widget_tree_hides_codes_without_changing_button_command(self) -> None:
        root = QWidget()
        layout = QVBoxLayout(root)
        label = QLabel("B121–B125 — ASYSTENT CODZIENNY")
        button = QPushButton("AUDYT B125")
        button.setProperty("command", "Uruchom audyt B125")
        layout.addWidget(label)
        layout.addWidget(button)
        clean_user_visible_widgets(root)
        self.assertFalse(contains_stage_code(label.text()))
        self.assertFalse(contains_stage_code(button.text()))
        self.assertEqual(button.property("command"), "Uruchom audyt B125")

    def test_client_and_voice_share_the_same_boundary(self) -> None:
        raw = "Wynik B130: REAL_ONLINE_ASSISTANT_RC_READY"
        client = ClientIsolationPolicy.sanitize_text(raw)
        spoken = PolishSpeechDirector().direct(raw).text
        self.assertFalse(contains_stage_code(client))
        self.assertFalse(contains_stage_code(spoken))
        self.assertNotIn("_", client)
        self.assertNotIn("_", spoken)

    def test_owner_commands_are_backgrounded_without_event_reentry(self) -> None:
        runtime = Path("app/gui/business_command_runtime.py").read_text(
            encoding="utf-8"
        )
        worker = Path("app/gui/owner_background_commands.py").read_text(
            encoding="utf-8"
        )
        window = Path("app/gui/main_window.py").read_text(encoding="utf-8")
        self.assertIn("start_owner_command(self, text)", runtime)
        self.assertIn("execute_owner_thought(self, thought)", runtime)
        self.assertNotIn("processEvents", runtime)
        self.assertIn("setMaxThreadCount(1)", worker)
        self.assertIn("self._owner_async_enabled = True", window)

    def test_service_snapshot_uses_cache_between_refreshes(self) -> None:
        calls = {"background": 0, "online": 0}

        def background() -> str:
            calls["background"] += 1
            return "READY"

        class Online:
            @staticmethod
            def status() -> dict:
                calls["online"] += 1
                return {"connection": {"token_present": True}}

        window = SimpleNamespace(
            _status_tick=0,
            _background_status=background,
            assistant=SimpleNamespace(online=Online()),
        )
        self.assertEqual(business_service_snapshot(window), ("READY", True))
        window._status_tick = 1
        self.assertEqual(business_service_snapshot(window), ("READY", True))
        self.assertEqual(calls, {"background": 1, "online": 1})


if __name__ == "__main__":
    unittest.main()
