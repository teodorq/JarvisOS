from __future__ import annotations

from datetime import datetime
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from app.natural_actions.service import NaturalActionService
from tests.test_b151_b155_daily_actions import FIXED_NOW, FakeOnline


class FarFutureWallClock(datetime):
    @classmethod
    def now(cls, tz=None):
        value = cls(2099, 1, 1, 12, 0)
        return value.replace(tzinfo=tz) if tz is not None else value


class B1731CalendarClockConsistencyTests(unittest.TestCase):
    def test_calendar_lookup_uses_injected_clock_not_wall_clock(self) -> None:
        with TemporaryDirectory() as directory:
            online = FakeOnline(directory)
            service = NaturalActionService(
                directory,
                online=online,
                now_provider=lambda: FIXED_NOW,
            )
            with patch(
                "app.natural_actions.advanced_actions.datetime",
                FarFutureWallClock,
            ):
                plan = service.plan("Usuń spotkanie z hydraulikiem")

        self.assertTrue(plan["requires_confirmation"])
        self.assertEqual(
            plan["natural_slots"]["event_id"],
            "event-plumber",
        )
        self.assertIn("Usunąć", plan["confirmation_message"])


if __name__ == "__main__":
    unittest.main()
