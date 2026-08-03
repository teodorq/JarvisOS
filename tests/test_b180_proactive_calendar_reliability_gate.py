from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.natural_actions.proactive_calendar_reliability_gate import (
    ProactiveCalendarReliabilityGate,
)
from app.natural_actions.service import NaturalActionService
from tests.test_b166_b170_active_resolution import FakeOnline


class B180ProactiveCalendarReliabilityGateTests(unittest.TestCase):
    @staticmethod
    def status() -> dict:
        with TemporaryDirectory() as directory:
            service = NaturalActionService(
                directory,
                online=FakeOnline(directory, events=[]),
            )
            return service.status()

    def test_current_runtime_passes_the_release_gate(self):
        report = ProactiveCalendarReliabilityGate.evaluate(self.status())
        self.assertTrue(report["ready"])
        self.assertEqual(
            report["status"],
            "B176_B180_PROACTIVE_CALENDAR_READY",
        )
        self.assertEqual(report["failed"], [])

    def test_all_stage_markers_are_exact(self):
        status = self.status()
        self.assertEqual(
            {
                name: status["stages"].get(name)
                for name in ProactiveCalendarReliabilityGate.REQUIRED_STAGES
            },
            ProactiveCalendarReliabilityGate.REQUIRED_STAGES,
        )

    def test_gate_blocks_automatic_write_or_missing_confirmation(self):
        status = deepcopy(self.status())
        status["writes_require_confirmation"] = False
        status["active_resolution"]["automatic_calendar_changes"] = True
        report = ProactiveCalendarReliabilityGate.evaluate(status)
        self.assertFalse(report["ready"])
        self.assertIn("writes_require_confirmation", report["failed"])
        self.assertIn("no_automatic_calendar_changes", report["failed"])

    def test_gate_blocks_duplicate_notification_regression(self):
        status = deepcopy(self.status())
        status["startup_notifications"][
            "duplicate_notifications_suppressed"
        ] = False
        status["proactive_brief_guard"][
            "duplicate_brief_suppressed"
        ] = False
        report = ProactiveCalendarReliabilityGate.evaluate(status)
        self.assertFalse(report["ready"])
        self.assertIn("new_or_changed_only", report["failed"])
        self.assertIn(
            "periodic_brief_duplicate_suppressed",
            report["failed"],
        )

    def test_release_config_matches_practical_contract(self):
        root = Path(__file__).resolve().parents[1]
        config = json.loads(
            (
                root
                / "config/b180_proactive_calendar_reliability_gate.json"
            ).read_text(encoding="utf-8")
        )
        gates = config["gates"]
        self.assertEqual(
            config["status"],
            "PROACTIVE_CALENDAR_RELIABILITY_GATE_READY",
        )
        self.assertEqual(gates["live_refresh_interval_seconds"], 60)
        self.assertEqual(gates["max_pending_alerts"], 1)
        self.assertTrue(gates["periodic_brief_fallback_suppressed"])
        self.assertTrue(gates["defer_during_confirmation"])
        self.assertFalse(gates["automatic_calendar_writes"])
        self.assertFalse(gates["voice_notifications"])

    def test_client_policy_is_nontechnical_and_silent(self):
        report = ProactiveCalendarReliabilityGate.evaluate(self.status())
        serialized = json.dumps(report, ensure_ascii=False).lower()
        self.assertEqual(
            report["client_policy"],
            "NONTECHNICAL_SILENT_ALERTS_ONLY",
        )
        for marker in ("traceback", "sha256", "c:/jarvisai"):
            self.assertNotIn(marker, serialized)

    def test_source_bounds_and_no_fixed_project_path(self):
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/natural_actions/proactive_calendar_reliability_gate.py": 100,
            "app/natural_actions/service.py": 320,
            "app/gui/client_online_mixin.py": 140,
            "tests/test_b180_proactive_calendar_reliability_gate.py": 150,
        }
        for relative, limit in limits.items():
            source = (root / relative).read_text(encoding="utf-8")
            self.assertLess(len(source.splitlines()), limit, relative)
            self.assertNotIn("C:" + "/JarvisAI", source.replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()
