from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from app.ai.software_engineer.autonomous_learning_engine import (
    AutonomousLearningEngine,
)
from app.ai.software_engineer.autonomy_history_collector import (
    AutonomyHistoryCollector,
)
from app.ai.software_engineer.full_autonomy_store import (
    FullAutonomyStore,
)
from app.ai.software_engineer.full_autonomy_workflow import (
    FullAutonomyWorkflow,
)


class MemoryRunStore:

    def __init__(self, run: dict):
        self.value = dict(run)
        self.path = Path("data/autodev/full_autonomy_runs.json")

    def get(self, run_id: str):
        if str(self.value.get("run_id")) != str(run_id):
            return None
        return dict(self.value)

    def save(self, run: dict):
        self.value = dict(run)
        return dict(self.value)


class DirectorStub:

    def __init__(self, result: dict):
        self.result = dict(result)

    def direct(self, *args, **kwargs):
        return dict(self.result)


class B522FailedRunLearningFixTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "app").mkdir()
        (self.root / "tests").mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def run_data(
        *,
        run_id: str = "autonomy-failed",
        status: str = "FULL_AUTONOMY_PLAN_READY",
    ) -> dict:
        return {
            "run_id": run_id,
            "goal_id": f"goal-{run_id}",
            "portfolio_id": f"portfolio-{run_id}",
            "objective": "Utwórz moduł demonstracyjny",
            "status": status,
            "success": status == "FULL_AUTONOMY_COMPLETED",
            "started_at": "2026-07-16T10:00:00+00:00",
            "completed_at": "",
            "policy": {
                "auto_execute": False,
                "auto_approve": False,
                "auto_rollback": True,
                "final_validation": True,
            },
            "plan": {
                "target_files": ["app/demo/models.py"],
                "subsystems": ["app.demo"],
                "campaigns": [{}, {}],
                "estimated_roi": 8.0,
                "estimated_risk": 3.0,
                "estimated_minutes": 20,
                "confidence": 0.8,
            },
            "execution": {
                "stages_total": 4,
                "changed_files": [],
                "progress_percent": 0.0,
            },
            "errors": [],
        }

    def workflow_for_resume(self, result: dict):
        run = self.run_data()
        workflow = FullAutonomyWorkflow.__new__(FullAutonomyWorkflow)
        workflow.store = MemoryRunStore(run)
        workflow.director = DirectorStub(result)
        workflow.learning_engine = SimpleNamespace(
            observe_run=MagicMock(
                return_value={
                    "success": True,
                    "status": "AUTONOMOUS_LEARNING_EPISODE_RECORDED",
                    "created": True,
                    "errors": [],
                }
            )
        )
        workflow._apply_learning_policy = lambda values: dict(values)
        workflow._event = lambda *args, **kwargs: None
        workflow._update_execution = lambda *args, **kwargs: None
        workflow._progress_callback = lambda run: None
        return workflow

    def test_failed_resume_records_learning_episode(self) -> None:
        workflow = self.workflow_for_resume({
            "success": False,
            "status": "CAMPAIGN_DIRECTOR_BLOCKED_BY_FAILED_DEPENDENCY",
            "portfolio": {},
            "director_run": {
                "run_id": "director-1",
                "retries": 1,
                "failures": 2,
            },
            "errors": ["Dependency failed"],
        })

        result = workflow.resume("autonomy-failed")

        self.assertEqual(result["status"], "FULL_AUTONOMY_FAILED")
        workflow.learning_engine.observe_run.assert_called_once()
        self.assertEqual(
            result["autonomy_run"]["learning_observation"]["status"],
            "AUTONOMOUS_LEARNING_EPISODE_RECORDED",
        )

    def test_paused_resume_does_not_record_terminal_episode(self) -> None:
        workflow = self.workflow_for_resume({
            "success": True,
            "status": "CAMPAIGN_DIRECTOR_PAUSED_CYCLE_LIMIT",
            "portfolio": {},
            "director_run": {"run_id": "director-2"},
            "errors": [],
        })

        result = workflow.resume("autonomy-failed")

        self.assertEqual(result["status"], "FULL_AUTONOMY_PAUSED")
        workflow.learning_engine.observe_run.assert_not_called()

    def test_manual_rollback_records_terminal_outcome(self) -> None:
        run = self.run_data(status="FULL_AUTONOMY_COMPLETED")
        run["completed_at"] = "2026-07-16T10:10:00+00:00"
        workflow = FullAutonomyWorkflow.__new__(FullAutonomyWorkflow)
        workflow.store = MemoryRunStore(run)
        workflow.portfolio_workflow = SimpleNamespace(
            rollback=lambda portfolio_id: {
                "success": True,
                "status": "MULTI_CAMPAIGN_ROLLED_BACK",
                "errors": [],
            }
        )
        workflow.learning_engine = SimpleNamespace(
            observe_run=MagicMock(
                return_value={
                    "success": True,
                    "status": "AUTONOMOUS_LEARNING_EPISODE_UPDATED",
                    "created": False,
                    "errors": [],
                }
            )
        )
        workflow._event = lambda *args, **kwargs: None
        workflow._update_execution = lambda *args, **kwargs: None

        result = workflow.rollback(run["run_id"])

        self.assertEqual(result["status"], "FULL_AUTONOMY_ROLLED_BACK")
        workflow.learning_engine.observe_run.assert_called_once()

    def test_status_backfills_missing_failed_run_once(self) -> None:
        full_store = FullAutonomyStore(self.root)
        failed = self.run_data(status="FULL_AUTONOMY_FAILED")
        failed["completed_at"] = "2026-07-16T10:10:00+00:00"
        failed["director_result"] = {
            "director_run": {"retries": 1, "failures": 2}
        }
        full_store.save(failed)
        engine = AutonomousLearningEngine(self.root)

        first = engine.status()
        second = engine.status()

        self.assertEqual(first["store"]["episodes"], 1)
        self.assertEqual(first["reconciliation"]["created"], 1)
        self.assertEqual(second["store"]["episodes"], 1)
        self.assertEqual(second["reconciliation"]["created"], 0)
        self.assertGreaterEqual(second["reconciliation"]["duplicates"], 1)

    def test_planning_failure_has_at_least_one_failure(self) -> None:
        collector = AutonomyHistoryCollector(self.root)
        run = self.run_data(status="FULL_AUTONOMY_PLANNING_FAILED")
        run["completed_at"] = "2026-07-16T10:01:00+00:00"
        run["plan"] = {}
        run["execution"] = {}
        run["errors"] = ["Existing module"]

        episode = collector.from_full_run(run)

        self.assertIsNotNone(episode)
        self.assertFalse(episode["success"])
        self.assertEqual(episode["failure_count"], 1)

    def test_failed_director_preserves_retry_and_failure_counts(self) -> None:
        collector = AutonomyHistoryCollector(self.root)
        run = self.run_data(status="FULL_AUTONOMY_FAILED")
        run["completed_at"] = "2026-07-16T10:10:00+00:00"
        run["director_result"] = {
            "director_run": {"retries": 1, "failures": 2}
        }

        episode = collector.from_full_run(run)

        self.assertEqual(episode["retry_count"], 1)
        self.assertEqual(episode["failure_count"], 2)
        self.assertFalse(episode["rolled_back"])

    def test_rolled_back_failure_is_recorded_without_new_identity(self) -> None:
        collector = AutonomyHistoryCollector(self.root)
        run = self.run_data(
            status="FULL_AUTONOMY_FINAL_VALIDATION_FAILED_AND_ROLLED_BACK"
        )
        run["completed_at"] = "2026-07-16T10:10:00+00:00"
        run["rollback"] = {"success": True}

        first = collector.from_full_run(run)
        run["errors"].append("Additional detail")
        second = collector.from_full_run(run)

        self.assertTrue(first["rolled_back"])
        self.assertEqual(first["failure_count"], 1)
        self.assertEqual(first["episode_id"], second["episode_id"])


if __name__ == "__main__":
    unittest.main()
