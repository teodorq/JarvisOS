from __future__ import annotations

from copy import deepcopy
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.natural_actions.reliability_release_gate import ReliabilityReleaseGate
from app.natural_actions.service import NaturalActionService
from tests.test_b166_b170_active_resolution import FakeOnline


class B175ReliabilityReleaseGateTests(unittest.TestCase):
    @staticmethod
    def status() -> dict:
        with TemporaryDirectory() as directory:
            service = NaturalActionService(
                directory,
                online=FakeOnline(directory, events=[]),
            )
            return service.status()

    def test_current_runtime_passes_the_release_gate(self):
        report = ReliabilityReleaseGate.evaluate(self.status())
        self.assertTrue(report["ready"])
        self.assertEqual(
            report["status"],
            "B171_B175_RELIABILITY_RELEASE_READY",
        )
        self.assertEqual(report["failed"], [])

    def test_all_stage_markers_are_exact(self):
        status = self.status()
        self.assertEqual(
            {
                name: status["stages"].get(name)
                for name in ReliabilityReleaseGate.REQUIRED_STAGES
            },
            ReliabilityReleaseGate.REQUIRED_STAGES,
        )

    def test_gate_blocks_when_confirmation_is_disabled(self):
        status = deepcopy(self.status())
        status["writes_require_confirmation"] = False
        report = ReliabilityReleaseGate.evaluate(status)
        self.assertFalse(report["ready"])
        self.assertIn("writes_require_confirmation", report["failed"])

    def test_gate_blocks_unbounded_retry_or_automatic_write(self):
        status = deepcopy(self.status())
        status["active_resolution"]["safe_retry_limit"] = 2
        status["active_resolution"]["automatic_calendar_changes"] = True
        report = ReliabilityReleaseGate.evaluate(status)
        self.assertFalse(report["ready"])
        self.assertIn("safe_retry_is_bounded", report["failed"])
        self.assertIn("no_automatic_calendar_changes", report["failed"])

    def test_release_config_matches_the_runtime_contract(self):
        root = Path(__file__).resolve().parents[1]
        config = json.loads(
            (root / "config/b175_reliability_release.json").read_text(
                encoding="utf-8"
            )
        )
        gates = config["gates"]
        self.assertEqual(config["status"], "RELIABILITY_RELEASE_GATE_READY")
        self.assertTrue(gates["confirmation_required"])
        self.assertTrue(gates["duplicate_protection"])
        self.assertEqual(gates["safe_retry_limit"], 1)
        self.assertTrue(gates["safe_undo"])
        self.assertFalse(gates["automatic_calendar_changes"])
        self.assertFalse(gates["automatic_mail_sending"])

    def test_client_policy_does_not_expose_owner_details(self):
        report = ReliabilityReleaseGate.evaluate(self.status())
        serialized = json.dumps(report, ensure_ascii=False)
        self.assertEqual(
            report["client_policy"],
            "NONTECHNICAL_MESSAGES_ONLY",
        )
        self.assertNotIn("C:" + "/JarvisAI", serialized)
        self.assertNotIn("traceback", serialized.lower())
        self.assertNotIn("sha256", serialized.lower())

    def test_source_bounds_and_no_fixed_project_path(self):
        root = Path(__file__).resolve().parents[1]
        limits = {
            "app/natural_actions/reliability_release_gate.py": 100,
            "app/natural_actions/service.py": 320,
            "tests/test_b175_reliability_release_gate.py": 140,
        }
        for relative, limit in limits.items():
            source = (root / relative).read_text(encoding="utf-8")
            self.assertLess(len(source.splitlines()), limit, relative)
            self.assertNotIn("C:" + "/JarvisAI", source.replace("\\", "/"))


if __name__ == "__main__":
    unittest.main()
