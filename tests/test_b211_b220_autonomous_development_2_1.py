from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import MagicMock

from app.ai.software_engineer.autonomous_backlog import AutonomousBacklogReader
from app.ai.software_engineer.autonomous_cycle_commands import (
    execute_autonomous_cycle_command,
    plan_autonomous_cycle_command,
)
from app.ai.software_engineer.autonomous_cycle_service import AutonomousBacklogCycleService
from app.ai.software_engineer.autonomous_cycle_store import AutonomousCycleStore
from app.ai.software_engineer.safe_autonomous_development_service import SafeAutonomousDevelopmentService


class B211B220AutonomousDevelopment21Tests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        for directory in ("app", "tests", "tools", "config", "data/autodev"):
            (self.root / directory).mkdir(parents=True, exist_ok=True)
        (self.root / "app/__init__.py").write_text("", encoding="utf-8")
        (self.root / "tests/__init__.py").write_text("", encoding="utf-8")
        self.target = self.root / "app/sample.py"
        self.original = (
            '"""Sample runtime module."""\n\n'
            "from __future__ import annotations\n\n"
            "def long_worker(value: int) -> int:\n"
            "    result = value\n"
            "    result += 1\n"
            "    return result\n"
        )
        self.target.write_text(self.original, encoding="utf-8")
        (self.root / "tests/test_sample.py").write_text(
            "import unittest\nfrom app.sample import long_worker\n\n"
            "class SampleTests(unittest.TestCase):\n"
            "    def test_worker(self):\n"
            "        self.assertEqual(long_worker(2), 3)\n",
            encoding="utf-8",
        )
        source = Path(__file__).resolve().parents[1]
        for name in ("safe_development_unittest_runner.py", "safe_development_import_runner.py"):
            shutil.copy2(source / "tools" / name, self.root / "tools" / name)
        for name in (
            "b201_b210_safe_autonomous_development_2.json",
            "b211_b220_autonomous_development_2_1.json",
        ):
            shutil.copy2(source / "config" / name, self.root / "config" / name)
        self._write_backlog()
        self.service = AutonomousBacklogCycleService(self.root)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def _write_backlog(self) -> None:
        candidate = {
            "opportunity_id": "opportunity-safe-1",
            "title": "Uprość długą funkcję",
            "objective": "Przygotuj bezpieczny pierwszy krok dla long_worker.",
            "target": "app/sample.py",
            "source": "test",
            "severity": "MEDIUM",
            "issue_type": "LONG_FUNCTION",
            "fingerprint": "fingerprint-safe-1",
            "value_score": 70,
            "risk_score": 20,
            "effort_score": 10,
            "confidence": 0.95,
            "final_score": 65,
            "status": "PENDING",
            "metadata": {"function": "long_worker", "function_lines": 90},
        }
        (self.root / "data/autodev/project_intelligence.json").write_text(
            json.dumps({
                "version": 1,
                "opportunities": {candidate["opportunity_id"]: candidate},
                "order": [candidate["opportunity_id"]],
            }),
            encoding="utf-8",
        )
        (self.root / "data/autodev/autonomous_task_queue.json").write_text(
            json.dumps({"version": 2, "tasks": []}), encoding="utf-8"
        )

    def test_b211_reads_and_normalizes_pending_backlog_task(self) -> None:
        items = AutonomousBacklogReader(self.root).candidates()
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0].target, "app/sample.py")
        self.assertEqual(items[0].metadata["function"], "long_worker")

    def test_b212_rejects_running_cancelled_and_unsafe_tasks(self) -> None:
        data = json.loads((self.root / "data/autodev/project_intelligence.json").read_text())
        item = data["opportunities"]["opportunity-safe-1"]
        item["status"] = "RUNNING"
        (self.root / "data/autodev/project_intelligence.json").write_text(json.dumps(data))
        self.assertEqual(AutonomousBacklogReader(self.root).candidates(), [])

    def test_b213_ranking_is_deterministic(self) -> None:
        first = [item.task_id for item in AutonomousBacklogReader(self.root).candidates()]
        second = [item.task_id for item in AutonomousBacklogReader(self.root).candidates()]
        self.assertEqual(first, second)

    def test_b214_claim_blocks_duplicate_cycle(self) -> None:
        store = AutonomousCycleStore(self.root)
        task = AutonomousBacklogReader(self.root).candidates()[0].to_dict()
        first = store.new_cycle()
        second = store.new_cycle()
        self.assertTrue(store.claim(first, task))
        self.assertFalse(store.claim(second, task))

    def test_b215_b216_cycle_prepares_exact_function_patch_on_copy(self) -> None:
        result = self.service.run_one()
        self.assertTrue(result["success"], result)
        self.assertEqual(result["status"], "READY_FOR_APPROVAL")
        cycle = result["cycle"]
        session = cycle["result"]["safe_session"]
        self.assertEqual(session["target"], "app/sample.py")
        self.assertEqual(session["transform"], "EXTRACT_FUNCTION_TAIL")
        self.assertTrue(
            session["validation"]["static"]["checks"]["goal_aligned"]
        )
        self.assertGreaterEqual(session["validation"]["workspace"]["tests"]["count"], 1)
        self.assertEqual(self.target.read_text(encoding="utf-8"), self.original)

    def test_b217_cycle_is_persistent_and_bound_to_safe_session(self) -> None:
        first = self.service.run_one()["cycle"]
        loaded = AutonomousCycleStore(self.root).load(first["cycle_id"])
        self.assertEqual(loaded.safe_session_id, first["safe_session_id"])
        self.assertEqual(loaded.operation_fingerprint, first["operation_fingerprint"])

    def test_b218_status_resume_and_cancel_are_idempotent(self) -> None:
        first = self.service.run_one()
        resumed = self.service.resume()
        self.assertTrue(resumed["duplicate"])
        self.assertEqual(
            resumed["cycle"]["cycle_id"], first["cycle"]["cycle_id"]
        )
        cancelled = self.service.cancel()
        self.assertEqual(cancelled["status"], "CANCELLED")
        self.assertEqual(self.target.read_text(encoding="utf-8"), self.original)

    def test_b219_completed_task_is_not_selected_again(self) -> None:
        result = self.service.run_one()
        cycle = AutonomousCycleStore(self.root).load(result["cycle"]["cycle_id"])
        cycle.status = "DEPLOYED"
        AutonomousCycleStore(self.root).save(cycle)
        AutonomousCycleStore(self.root).mark_completed(cycle)
        self.assertEqual(AutonomousBacklogReader(self.root).candidates(
            excluded_fingerprints=AutonomousCycleStore(self.root).excluded_fingerprints()
        ), [])

    def test_b220_natural_route_precedes_legacy_autodev_and_never_deploys(self) -> None:
        brain = MagicMock()
        brain.project_root = self.root
        thought = plan_autonomous_cycle_command(
            brain,
            "Uruchom jeden bezpieczny cykl AutoDev z backlogu i zatrzymaj się przed wdrożeniem.",
        )
        self.assertEqual(thought["handler"], "autonomous_cycle_run")
        self.assertFalse(thought["requires_confirmation"])
        self.assertFalse(thought["project_write"])
        message = execute_autonomous_cycle_command(brain, thought)
        self.assertIn("Działający projekt nie został zmieniony", message)

    def test_b220_policy_and_source_contracts_are_bounded(self) -> None:
        source = Path(__file__).resolve().parents[1]
        config = json.loads(
            (source / "config/b211_b220_autonomous_development_2_1.json").read_text()
        )
        self.assertFalse(config["safety"]["auto_approve"])
        self.assertFalse(config["safety"]["auto_deploy"])
        self.assertTrue(config["safety"]["stop_before_deployment"])
        limits = {
            "app/ai/software_engineer/autonomous_cycle_models.py": 150,
            "app/ai/software_engineer/autonomous_backlog.py": 320,
            "app/ai/software_engineer/autonomous_cycle_store.py": 320,
            "app/ai/software_engineer/autonomous_cycle_service.py": 330,
            "app/ai/software_engineer/autonomous_cycle_commands.py": 220,
        }
        for relative, maximum in limits.items():
            text = (source / relative).read_text(encoding="utf-8")
            self.assertLess(len(text.splitlines()), maximum, relative)
            self.assertNotIn("C:\\JarvisAI", text)


if __name__ == "__main__":
    unittest.main()
