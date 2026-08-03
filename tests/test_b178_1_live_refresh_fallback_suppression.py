from __future__ import annotations

from pathlib import Path
import unittest

from app.natural_actions.proactive_conflict_brief_guard import (
    ProactiveConflictBriefGuard,
)


class B1781LiveRefreshFallbackSuppressionTests(unittest.TestCase):
    @staticmethod
    def conflict(*, should_show=True, reactivated=False):
        return {
            "should_show": should_show,
            "scan_completed": True,
            "conflict_count": 1,
            "fingerprint": "conflict-123",
            "reactivated_after_undo": reactivated,
            "automatic_writes": False,
        }

    def test_same_conflict_suppresses_periodic_daily_brief(self):
        decision = ProactiveConflictBriefGuard.evaluate(
            self.conflict(),
            {"active_fingerprint": "conflict-123"},
        )
        self.assertTrue(decision["suppress"])
        self.assertEqual(decision["reason"], "unchanged")

    def test_decision_suppressed_conflict_cannot_reappear_in_brief(self):
        decision = ProactiveConflictBriefGuard.evaluate(
            self.conflict(should_show=False),
            {"active_fingerprint": ""},
        )
        self.assertTrue(decision["suppress"])
        self.assertEqual(decision["reason"], "suppressed_by_decision")

    def test_changed_conflict_is_allowed(self):
        decision = ProactiveConflictBriefGuard.evaluate(
            self.conflict(),
            {"active_fingerprint": "old-conflict"},
        )
        self.assertFalse(decision["suppress"])
        self.assertEqual(decision["reason"], "new")

    def test_reactivated_conflict_is_allowed(self):
        decision = ProactiveConflictBriefGuard.evaluate(
            self.conflict(reactivated=True),
            {"active_fingerprint": "conflict-123"},
        )
        self.assertFalse(decision["suppress"])
        self.assertEqual(decision["reason"], "changed")

    def test_quiet_or_transient_scan_does_not_block_useful_brief(self):
        quiet = ProactiveConflictBriefGuard.evaluate(
            {
                "should_show": False,
                "scan_completed": True,
                "conflict_count": 0,
                "fingerprint": "",
            },
            {"active_fingerprint": ""},
        )
        transient = ProactiveConflictBriefGuard.evaluate(
            {
                "should_show": False,
                "scan_completed": False,
                "conflict_count": 0,
                "fingerprint": "",
            },
            {"active_fingerprint": ""},
        )
        self.assertFalse(quiet["suppress"])
        self.assertFalse(transient["suppress"])

    def test_service_and_client_timer_use_guard_before_daily_brief(self):
        root = Path(__file__).resolve().parents[1]
        service = (root / "app/natural_actions/service.py").read_text(
            encoding="utf-8"
        )
        mixin = (root / "app/gui/client_online_mixin.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("def proactive_brief_guard", service)
        self.assertIn("ProactiveConflictBriefGuard.evaluate", service)
        self.assertLess(
            mixin.index('result = natural.startup_brief()'),
            mixin.index('if result.get("speak")'),
        )
        guard_index = mixin.index('guard = getattr(natural, "proactive_brief_guard"')
        brief_index = mixin.index("result = natural.startup_brief()")
        self.assertLess(guard_index, brief_index)
        self.assertIn('if decision.get("suppress"):', mixin)

    def test_fix_is_read_only_and_sources_are_bounded(self):
        root = Path(__file__).resolve().parents[1]
        files = [
            root / "app/natural_actions/proactive_conflict_brief_guard.py",
            root / "app/gui/client_online_mixin.py",
        ]
        for path in files:
            source = path.read_text(encoding="utf-8")
            for marker in (
                "create_event(",
                "update_event(",
                "delete_event(",
                "move_event(",
            ):
                self.assertNotIn(marker, source)
        guard_source = files[0].read_text(encoding="utf-8")
        self.assertNotIn("say_safe(", guard_source)
        self.assertLess(len(guard_source.splitlines()), 90)


if __name__ == "__main__":
    unittest.main()
