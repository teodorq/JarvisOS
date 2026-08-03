from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from app.ai.software_engineer.autonomous_backlog import AutonomousBacklogReader
from app.ai.software_engineer.autonomous_cycle_service import (
    AutonomousBacklogCycleService,
)
from app.ai.software_engineer.autonomous_self_seeding import (
    AutonomousBacklogSelfSeeder,
    AutonomousSelfSeedStore,
)


class B2202EmptyBacklogSelfSeedingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        for directory in (
            "app",
            "tests",
            "tools",
            "config",
            "data/autodev",
        ):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        (self.root / "app/__init__.py").write_text("", encoding="utf-8")
        (self.root / "tests/__init__.py").write_text("", encoding="utf-8")
        self.target = self.root / "app/sample.py"
        body = "".join(f"    value += {index % 2}\n" for index in range(122))
        self.original = (
            '"""Sample runtime module."""\n\n'
            "from __future__ import annotations\n\n"
            "def long_worker(value: int) -> int:\n"
            + body
            + "    return value\n"
        )
        self.target.write_text(self.original, encoding="utf-8")
        (self.root / "tests/test_sample.py").write_text(
            "import unittest\nfrom app.sample import long_worker\n\n"
            "class SampleTests(unittest.TestCase):\n"
            "    def test_worker(self):\n"
            "        self.assertEqual(long_worker(2), 63)\n",
            encoding="utf-8",
        )
        source = Path(__file__).resolve().parents[1]
        for name in (
            "safe_development_unittest_runner.py",
            "safe_development_import_runner.py",
        ):
            shutil.copy2(source / "tools" / name, self.root / "tools" / name)
        for name in (
            "b201_b210_safe_autonomous_development_2.json",
            "b211_b220_autonomous_development_2_1.json",
            "b220_2_empty_backlog_self_seeding.json",
        ):
            shutil.copy2(source / "config" / name, self.root / "config" / name)
        self.intelligence = self.root / "data/autodev/project_intelligence.json"
        self.queue = self.root / "data/autodev/autonomous_task_queue.json"
        self.intelligence.write_text(
            json.dumps({
                "version": 1,
                "opportunities": {
                    "old": {
                        "opportunity_id": "old",
                        "target": "app/sample.py",
                        "status": "COMPLETED",
                        "risk_score": 20,
                        "confidence": 0.95,
                        "final_score": 60,
                    }
                },
                "order": ["old"],
            }),
            encoding="utf-8",
        )
        self.queue.write_text(
            json.dumps({"version": 2, "tasks": []}),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    @staticmethod
    def _hash(path: Path) -> str:
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def test_b220_2_scans_and_creates_one_low_risk_seed(self) -> None:
        result = AutonomousBacklogSelfSeeder(self.root).seed_one()
        self.assertTrue(result["success"], result)
        self.assertEqual(result["status"], "SELF_SEEDED")
        self.assertEqual(result["task"]["target"], "app/sample.py")
        self.assertEqual(result["task"]["metadata"]["function"], "long_worker")
        self.assertFalse(result["legacy_backlog_modified"])

    def test_b220_2_reader_normalizes_self_seeded_task(self) -> None:
        AutonomousBacklogSelfSeeder(self.root).seed_one()
        items = AutonomousBacklogReader(self.root).candidates()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].source, "self_seeded_project_scan")
        self.assertEqual(items[0].status, "PENDING")

    def test_b220_2_full_cycle_reaches_approval_stop(self) -> None:
        result = AutonomousBacklogCycleService(self.root).run_one()
        self.assertTrue(result["success"], result)
        self.assertEqual(result["status"], "READY_FOR_APPROVAL")
        cycle = result["cycle"]
        self.assertTrue(cycle["result"]["self_seeded"])
        self.assertEqual(cycle["task"]["target"], "app/sample.py")
        session = cycle["result"]["safe_session"]
        self.assertEqual(session["transform"], "EXTRACT_FUNCTION_TAIL")
        self.assertTrue(
            session["validation"]["static"]["checks"]["goal_aligned"]
        )
        self.assertGreaterEqual(
            session["validation"]["workspace"]["tests"]["count"],
            1,
        )
        self.assertEqual(self.target.read_text(encoding="utf-8"), self.original)

    def test_b220_2_legacy_backlogs_remain_byte_identical(self) -> None:
        before = (self._hash(self.intelligence), self._hash(self.queue))
        AutonomousBacklogCycleService(self.root).run_one()
        after = (self._hash(self.intelligence), self._hash(self.queue))
        self.assertEqual(after, before)

    def test_b220_2_seed_store_is_separate_and_bounded(self) -> None:
        AutonomousBacklogSelfSeeder(self.root).seed_one()
        store = AutonomousSelfSeedStore(self.root)
        self.assertEqual(len(store.tasks()), 1)
        self.assertIn(
            "autonomous_development_2_1/self_seeded_tasks.json",
            store.path.as_posix(),
        )

    def test_b220_2_duplicate_run_returns_same_active_cycle(self) -> None:
        service = AutonomousBacklogCycleService(self.root)
        first = service.run_one()
        second = service.run_one()
        self.assertTrue(second["duplicate"])
        self.assertEqual(
            first["cycle"]["cycle_id"],
            second["cycle"]["cycle_id"],
        )
        self.assertEqual(len(AutonomousSelfSeedStore(self.root).tasks()), 1)

    def test_b220_2_fingerprint_is_bound_to_source_hash(self) -> None:
        first = AutonomousBacklogSelfSeeder(self.root).seed_one()["task"]
        self.target.write_text(self.original + "\n", encoding="utf-8")
        second = AutonomousBacklogSelfSeeder(self.root).seed_one()["task"]
        self.assertNotEqual(first["fingerprint"], second["fingerprint"])

    def test_b220_2_rejects_scan_without_exact_safe_transform(self) -> None:
        fake = {
            "success": True,
            "files_scanned": 1,
            "prioritization": {
                "candidates": [{
                    "task": {
                        "title": "Duży moduł",
                        "description": "Brak małego kroku.",
                        "target": "app/sample.py",
                        "metadata": {
                            "issue_type": "LARGE_MODULE",
                            "confidence": 0.95,
                        },
                    },
                    "predicted_risk": 45,
                    "value_score": 70,
                    "effort_score": 20,
                    "final_score": 50,
                    "decision": "READY_FOR_SAFE_GENERATION",
                }],
            },
        }
        with patch(
            "app.ai.software_engineer.autonomous_self_seeding."
            "ProjectOpportunityScanner.run_cycle",
            return_value=fake,
        ):
            result = AutonomousBacklogSelfSeeder(self.root).seed_one()
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "NO_SAFE_SEED_CANDIDATE")

    def test_b220_2_policy_keeps_approval_and_deployment_disabled(self) -> None:
        source = Path(__file__).resolve().parents[1]
        config = json.loads(
            (source / "config/b220_2_empty_backlog_self_seeding.json").read_text()
        )
        self.assertTrue(config["safety"]["legacy_backlog_read_only"])
        self.assertFalse(config["safety"]["auto_approve"])
        self.assertFalse(config["safety"]["auto_deploy"])
        self.assertTrue(config["safety"]["stop_before_deployment"])

    def test_b220_2_source_contracts_are_bounded(self) -> None:
        source = Path(__file__).resolve().parents[1]
        limits = {
            "app/ai/software_engineer/autonomous_self_seeding.py": 280,
            "app/ai/software_engineer/autonomous_backlog.py": 300,
            "app/ai/software_engineer/autonomous_cycle_service.py": 330,
        }
        for relative, maximum in limits.items():
            text = (source / relative).read_text(encoding="utf-8")
            self.assertLess(len(text.splitlines()), maximum, relative)
            self.assertNotIn("C:\\JarvisAI", text)


if __name__ == "__main__":
    unittest.main()
