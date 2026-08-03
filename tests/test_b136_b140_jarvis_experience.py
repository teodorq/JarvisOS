from __future__ import annotations

import unittest

from app.jarvis_experience.isolation import ClientIsolationPolicy
from app.jarvis_experience.smart_task_loop import SmartTaskLoop


class FakeBrain:
    def __init__(self, thought=None, result="Zadanie wykonane."):
        self.thought = thought or {"can_execute": True, "actions": [{"action_type": "OPEN_APP"}]}
        self.result = result

    def think(self, _text):
        return dict(self.thought)

    def execute(self, _thought):
        return self.result


class TestB136B140JarvisExperience(unittest.TestCase):
    def test_client_event_has_only_public_fields(self):
        clean = ClientIsolationPolicy.sanitize_event({
            "state": "success", "message": "Gotowe", "progress": 120,
            "traceback": "secret", "path": r"C:\\JarvisAI\\data",
        })
        self.assertEqual(set(clean), {"state", "message", "progress", "requires_confirmation"})
        self.assertEqual(clean["progress"], 100)

    def test_technical_details_are_not_visible(self):
        text = ClientIsolationPolicy.sanitize_text(
            r"Traceback error_id abcdef1234567890 C:\\JarvisAI\\app\\brain.py"
        )
        self.assertNotIn("JarvisAI", text)
        self.assertNotIn("Traceback", text)

    def test_safe_task_executes_and_returns_friendly_result(self):
        loop = SmartTaskLoop(FakeBrain(), lambda _c, _r: {"allowed": True}, lambda _t: True)
        outcome = loop.prepare("otwórz kalendarz")
        self.assertEqual(outcome.status, "COMPLETED")
        self.assertEqual(outcome.message, "Zadanie wykonane.")

    def test_risky_task_requires_confirmation(self):
        loop = SmartTaskLoop(FakeBrain(), lambda _c, _r: {"allowed": True}, lambda _t: False)
        outcome = loop.prepare("wykonaj ważną zmianę")
        self.assertTrue(outcome.requires_confirmation)
        self.assertEqual(outcome.status, "CONFIRM")

    def test_denied_task_has_no_technical_reason(self):
        loop = SmartTaskLoop(FakeBrain(), lambda _c, _r: {"allowed": False, "reason": "ADMIN_DEBUG"}, lambda _t: True)
        outcome = loop.prepare("polecenie")
        self.assertEqual(outcome.status, "DENIED")
        self.assertNotIn("DEBUG", outcome.message)


if __name__ == "__main__":
    unittest.main()
