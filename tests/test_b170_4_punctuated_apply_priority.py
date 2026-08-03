from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from app.gui.active_resolution_priority import (
    active_resolution_priority_thought,
)
from app.natural_actions.service import NaturalActionService
from tests.test_b166_b170_active_resolution import FakeOnline


class _Memory:
    def last_suggestion(self):
        return {"kind": "calendar_move", "event_id": "event-b"}


class _NaturalStub:
    def __init__(self):
        self.runtime = SimpleNamespace(
            active=SimpleNamespace(memory=_Memory())
        )
        self.received = []

    def plan(self, command):
        self.received.append(str(command))
        return {
            "natural_action": True,
            "assistant_intent": "active_apply_suggestion",
            "can_execute": True,
            "read_only": False,
        }


class B1704PunctuatedApplyPriorityTests(unittest.TestCase):
    def test_owner_priority_accepts_sentence_punctuation(self):
        for command in (
            "Zrób to.",
            "Zrób to!",
            "  ZRÓB TO?  ",
            "zrób, to",
        ):
            with self.subTest(command=command):
                natural = _NaturalStub()
                window = SimpleNamespace(
                    assistant=SimpleNamespace(natural_actions=natural)
                )
                thought = active_resolution_priority_thought(window, command)
                self.assertIsNotNone(thought)
                self.assertEqual(
                    thought["assistant_intent"],
                    "active_apply_suggestion",
                )
                self.assertEqual(natural.received, [command])

    def test_real_natural_service_accepts_zrob_to_with_period(self):
        with TemporaryDirectory() as directory:
            now = datetime.now().astimezone().replace(microsecond=0)
            start = (now + timedelta(days=1)).replace(
                hour=18, minute=0, second=0
            )
            events = [
                {
                    "id": "event-a",
                    "title": "Spotkanie A",
                    "start_at": start.isoformat(),
                    "end_at": (start + timedelta(hours=1)).isoformat(),
                },
                {
                    "id": "event-b",
                    "title": "Spotkanie B",
                    "start_at": (start + timedelta(minutes=45)).isoformat(),
                    "end_at": (start + timedelta(minutes=105)).isoformat(),
                },
            ]
            service = NaturalActionService(
                directory,
                online=FakeOnline(directory, events=events),
            )
            advice = service.handle("Co mam zrobić z tym konfliktem?")
            self.assertIn("zrób to", advice.casefold())

            thought = service.plan("Zrób to.")

        self.assertEqual(
            thought["assistant_intent"],
            "active_apply_suggestion",
        )
        self.assertTrue(thought["requires_confirmation"])
        self.assertEqual(
            thought["natural_slots"]["event_id"],
            "event-b",
        )

    def test_source_limits_and_no_hardcoded_project_path(self):
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/gui/active_resolution_priority.py": 80,
            "app/natural_actions/active_understanding.py": 180,
        }
        for relative, limit in limits.items():
            source = (root / relative).read_text(encoding="utf-8")
            self.assertLess(len(source.splitlines()), limit, relative)
            self.assertNotIn("C:/JarvisAI", source.replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()
