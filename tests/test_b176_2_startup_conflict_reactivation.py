from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from app.natural_actions.active_resolution_memory import ActiveResolutionMemory
from app.natural_actions.startup_conflict_reactivation import (
    reactivate_after_verified_undo,
)


class _Analyzer:
    @staticmethod
    def dt(value):
        return datetime.fromisoformat(str(value))


class _Ledger:
    def __init__(self, rows):
        self.rows = list(rows)

    def _items(self):
        return list(self.rows)


class B1762StartupConflictReactivationTests(unittest.TestCase):
    def issue(self):
        start = datetime.now().astimezone().replace(microsecond=0)
        return {
            "type": "conflict",
            "fingerprint": "restored-conflict",
            "first": {"id": "a", "start_at": start.isoformat()},
            "second": {
                "id": "b",
                "start_at": (start + timedelta(minutes=30)).isoformat(),
            },
        }

    def active(self, root, rows):
        return SimpleNamespace(
            analyzer=_Analyzer(),
            memory=ActiveResolutionMemory(root),
            move_executor=SimpleNamespace(ledger=_Ledger(rows)),
        )

    def test_verified_undo_clears_completed_decision(self):
        with TemporaryDirectory() as directory:
            issue = self.issue()
            active = self.active(directory, [{
                "event_id": "b",
                "original_start": issue["second"]["start_at"],
                "undo_status": "COMPLETED",
            }])
            active.memory.decide(issue["fingerprint"], "completed")
            action = reactivate_after_verified_undo(
                active, issue, "completed", {"scan_completed": True}
            )
            self.assertEqual(action, "")
            self.assertEqual(active.memory.decision(issue["fingerprint"]), {})
            self.assertEqual(
                active.memory.last_issue()["fingerprint"],
                issue["fingerprint"],
            )

    def test_non_undone_completed_issue_stays_suppressed(self):
        with TemporaryDirectory() as directory:
            issue = self.issue()
            active = self.active(directory, [{
                "event_id": "b",
                "original_start": issue["second"]["start_at"],
                "undo_status": "",
            }])
            self.assertEqual(
                reactivate_after_verified_undo(
                    active, issue, "completed", {"scan_completed": True}
                ),
                "completed",
            )

    def test_different_restored_time_does_not_clear_decision(self):
        with TemporaryDirectory() as directory:
            issue = self.issue()
            different = (
                datetime.fromisoformat(issue["second"]["start_at"])
                + timedelta(hours=1)
            ).isoformat()
            active = self.active(directory, [{
                "event_id": "b",
                "original_start": different,
                "undo_status": "COMPLETED",
            }])
            active.memory.decide(issue["fingerprint"], "completed")
            action = reactivate_after_verified_undo(
                active, issue, "completed", {"scan_completed": True}
            )
            self.assertEqual(action, "completed")
            self.assertEqual(
                active.memory.decision(issue["fingerprint"])["action"],
                "completed",
            )

    def test_ignored_decision_is_not_reopened(self):
        with TemporaryDirectory() as directory:
            issue = self.issue()
            active = self.active(directory, [])
            self.assertEqual(
                reactivate_after_verified_undo(
                    active, issue, "ignored", {"scan_completed": True}
                ),
                "ignored",
            )

    def test_fix_is_read_only(self):
        root = Path(__file__).resolve().parents[1]
        source = (
            root / "app/natural_actions/startup_conflict_reactivation.py"
        ).read_text(encoding="utf-8")
        self.assertNotIn("update_event", source)
        self.assertNotIn("create_event", source)
        self.assertNotIn("delete_event", source)

    def test_runtime_filter_uses_reactivation(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / "app/natural_actions/active_resolution.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("reactivate_after_verified_undo(", source)

    def test_source_bounds(self):
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/natural_actions/active_resolution_memory.py": 120,
            "app/natural_actions/startup_conflict_reactivation.py": 60,
            "app/natural_actions/active_resolution.py": 360,
        }
        for relative, limit in limits.items():
            lines = (root / relative).read_text(encoding="utf-8").splitlines()
            self.assertLess(len(lines), limit, relative)


if __name__ == "__main__":
    unittest.main()
