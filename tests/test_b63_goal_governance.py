from __future__ import annotations

from datetime import datetime, timedelta, timezone
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock
import unittest

from app.ai.software_engineer.autonomy_governance_store import AutonomyGovernanceStore
from app.ai.software_engineer.goal_governance_service import GoalGovernanceService
from app.ai.software_engineer.strategic_development_models import StrategicDevelopmentGoal
from app.ai.software_engineer.strategic_development_store import StrategicDevelopmentStore


class B63GoalGovernanceTests(unittest.TestCase):
    def _service(self, directory):
        goal_store = StrategicDevelopmentStore(directory)
        portfolio_store = MagicMock()
        portfolio_store.summary.return_value = {"total": 0}
        portfolio = SimpleNamespace(
            store=portfolio_store,
            rebalance=MagicMock(return_value={"success": True}),
        )
        service = GoalGovernanceService(
            directory,
            store=AutonomyGovernanceStore(directory),
            strategic_development=SimpleNamespace(store=goal_store),
            strategic_portfolio=portfolio,
        )
        return service, goal_store, portfolio

    def _goal(self, goal_id, fingerprint, subsystem="app/ai", status="PENDING", updated_at=""):
        item = StrategicDevelopmentGoal(
            goal_id=goal_id,
            fingerprint=fingerprint,
            title=f"Goal {goal_id}",
            objective="Improve",
            subsystem=subsystem,
            issue_type="MAINTENANCE",
            status=status,
            priority_score=50.0,
            confidence=0.8,
        )
        value = item.to_dict()
        if updated_at:
            value["updated_at"] = updated_at
            value["created_at"] = updated_at
        return value

    def test_duplicate_goal_is_rejected(self):
        with TemporaryDirectory() as directory:
            service, store, _ = self._service(directory)
            store.save_goal(self._goal("g1", "same"))
            store.save_goal(self._goal("g2", "same"))
            result = service.run_cycle()
            statuses = {store.get_goal("g1")["status"], store.get_goal("g2")["status"]}
            self.assertIn("REJECTED", statuses)
            self.assertEqual(result["rejected"], 1)

    def test_active_duplicate_is_preserved(self):
        with TemporaryDirectory() as directory:
            service, store, _ = self._service(directory)
            store.save_goal(self._goal("g1", "same", status="ACTIVE"))
            store.save_goal(self._goal("g2", "same", status="PENDING"))
            service.run_cycle()
            self.assertEqual(store.get_goal("g1")["status"], "ACTIVE")

    def test_subsystem_quota_rejects_excess(self):
        with TemporaryDirectory() as directory:
            service, store, _ = self._service(directory)
            service.update_policy({"max_ready_goals_per_subsystem": 2})
            for index in range(4):
                goal = self._goal(f"g{index}", f"fp{index}")
                goal["priority_score"] = 100 - index
                store.save_goal(goal)
            result = service.run_cycle()
            self.assertGreaterEqual(result["rejected"], 2)

    def test_stale_blocked_goal_is_rejected(self):
        with TemporaryDirectory() as directory:
            service, store, _ = self._service(directory)
            old = (datetime.now(timezone.utc) - timedelta(days=90)).isoformat()
            store.save_goal(self._goal("g1", "fp", status="BLOCKED", updated_at=old))
            service.run_cycle()
            self.assertEqual(store.get_goal("g1")["status"], "REJECTED")

    def test_completed_goal_is_preserved(self):
        with TemporaryDirectory() as directory:
            service, store, _ = self._service(directory)
            store.save_goal(self._goal("g1", "same", status="COMPLETED"))
            store.save_goal(self._goal("g2", "same", status="PENDING"))
            service.run_cycle()
            self.assertEqual(store.get_goal("g1")["status"], "COMPLETED")

    def test_rebalance_runs_after_actions(self):
        with TemporaryDirectory() as directory:
            service, store, portfolio = self._service(directory)
            store.save_goal(self._goal("g1", "same"))
            store.save_goal(self._goal("g2", "same"))
            service.run_cycle()
            portfolio.rebalance.assert_called_once()

    def test_policy_never_auto_approves(self):
        with TemporaryDirectory() as directory:
            service, _, _ = self._service(directory)
            result = service.update_policy({"auto_approve": True})
            self.assertFalse(result["policy"]["auto_approve"])

    def test_status_reports_b63(self):
        with TemporaryDirectory() as directory:
            service, _, _ = self._service(directory)
            self.assertEqual(service.status()["stage"], "B63")


if __name__ == "__main__":
    unittest.main()
