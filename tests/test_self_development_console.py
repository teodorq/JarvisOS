from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.gui.self_development_console import (
    SelfDevelopmentConsoleSession,
    is_real_development_thought,
)


class TestSelfDevelopmentConsole(unittest.TestCase):
    def test_only_real_development_opens_python_monitor(self) -> None:
        self.assertFalse(is_real_development_thought({
            "handler": "self_improvement_advice",
            "can_execute": True,
        }))
        self.assertFalse(is_real_development_thought({
            "handler": "safe_development_status",
            "can_execute": True,
            "read_only": True,
        }))
        self.assertTrue(is_real_development_thought({
            "handler": "safe_development_prepare",
            "can_execute": True,
            "workspace_only": True,
        }))

    def test_monitor_records_truthful_start_progress_and_result(self) -> None:
        with TemporaryDirectory() as temporary:
            session = SelfDevelopmentConsoleSession.start(
                temporary,
                {
                    "handler": "safe_development_prepare",
                    "can_execute": True,
                    "workspace_only": True,
                    "plan": ["Przygotuj izolowaną kopię", "Uruchom testy"],
                },
            )
            self.assertIsNotNone(session)
            session.publish("WYKONANIE", "Python pracuje")
            session.publish("GOTOWE", "Poprawka przygotowana", terminal=True)
            events = [
                json.loads(line)
                for line in Path(session.log_path).read_text(
                    encoding="utf-8"
                ).splitlines()
            ]
        self.assertEqual([event["stage"] for event in events], [
            "START", "WYKONANIE", "GOTOWE",
        ])
        self.assertEqual(
            events[0]["details"]["plan"][0],
            "Przygotuj izolowaną kopię",
        )
        self.assertTrue(events[-1]["terminal"])


if __name__ == "__main__":
    unittest.main()
