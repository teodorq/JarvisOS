"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import unittest

from app.ai.brain_response_formatter import BrainResponseFormatter
from app.ai.software_engineer.autonomous_software_engineer import (
    AutonomousSoftwareEngineerController,
)
from app.ai.software_engineer.software_engineer_strategic_execution_router import (
    SoftwareEngineerStrategicExecutionRouter,
)
from app.ai.software_engineer.software_engineer_strategic_portfolio_formatter import (
    format_strategic_portfolio_response,
)
from app.ai.software_engineer.software_engineer_strategic_portfolio_router import (
    SoftwareEngineerStrategicPortfolioRouter,
)
from app.ai.software_engineer.strategic_execution_service import (
    StrategicExecutionService,
)
from app.ai.software_engineer.strategic_portfolio_models import (
    StrategicPortfolioEntry,
    StrategicPortfolioPolicy,
)
from app.ai.software_engineer.strategic_portfolio_optimizer import (
    StrategicPortfolioOptimizer,
)
from app.ai.software_engineer.strategic_portfolio_service import (
    StrategicPortfolioService,
)
from app.ai.software_engineer.strategic_portfolio_store import (
    StrategicPortfolioStore,
)
from app.gui.command_safety import is_read_only_learning_command


NOW = datetime(2026, 7, 17, 20, 0, tzinfo=timezone.utc)


def goal(
    goal_id: str,
    *,
    subsystem: str = "app/ai",
    score: float = 50.0,
    status: str = "PENDING",
    pending: int = 2,
) -> dict:
    return {
        "goal_id": goal_id,
        "title": f"Goal {goal_id}",
        "subsystem": subsystem,
        "issue_type": "LONG_FUNCTION",
        "status": status,
        "priority_score": score,
        "value_score": 70.0,
        "risk_score": 20.0,
        "confidence": 0.8,
        "pending_count": pending,
        "opportunity_ids": [f"opp-{goal_id}"],
    }


def execution(
    goal_id: str,
    status: str,
    index: int,
) -> dict:
    return {
        "execution_id": f"exec-{goal_id}-{index}",
        "goal_id": goal_id,
        "opportunity_id": f"opp-{goal_id}",
        "job_id": f"longrun-{goal_id}-{index}",
        "status": status,
        "updated_at": (
            NOW - timedelta(minutes=index)
        ).isoformat(),
    }


class FakeProjectStore:
    def __init__(self, opportunities: list[dict]) -> None:
        self.opportunities = list(opportunities)

    def policy(self) -> dict:
        return {
            "min_score": 25.0,
            "max_risk": 65.0,
            "min_confidence": 0.3,
        }

    def list_opportunities(self, *, limit: int = 1000) -> list[dict]:
        return [dict(item) for item in self.opportunities[:limit]]

    def summary(self) -> dict:
        return {
            "total": len(self.opportunities),
            "pending": len(self.opportunities),
            "active": 0,
        }


class FakeRanker:
    def select_best(self, values: list[dict], **_: object) -> dict | None:
        candidates = [
            dict(item)
            for item in values
            if str(item.get("status", "PENDING")).upper() == "PENDING"
        ]
        candidates.sort(
            key=lambda item: float(item.get("final_score", 0.0)),
            reverse=True,
        )
        return candidates[0] if candidates else None


class FakeProjectIntelligence:
    def __init__(self, opportunities: list[dict]) -> None:
        self.store = FakeProjectStore(opportunities)
        self.ranker = FakeRanker()


class FakeGoalStore:
    def __init__(self, goals: list[dict]) -> None:
        self.goals = {str(item["goal_id"]): dict(item) for item in goals}
        self.runtime_value = {
            "enabled": True,
            "paused": False,
            "active_goal_id": "",
        }

    def list_goals(self, *, limit: int = 1000) -> list[dict]:
        return [dict(item) for item in list(self.goals.values())[:limit]]

    def get_goal(self, goal_id: str) -> dict | None:
        item = self.goals.get(str(goal_id))
        return dict(item) if item else None

    def summary(self) -> dict:
        values = list(self.goals.values())
        return {
            "total": len(values),
            "pending": sum(item.get("status") == "PENDING" for item in values),
            "active": sum(item.get("status") == "ACTIVE" for item in values),
            "completed": 0,
            "blocked": 0,
        }

    def policy(self) -> dict:
        return {
            "min_goal_score": 15.0,
            "max_goal_risk": 65.0,
            "min_goal_confidence": 0.3,
        }

    def update_runtime(self, updates: dict) -> dict:
        self.runtime_value.update(dict(updates))
        return dict(self.runtime_value)

    def runtime(self) -> dict:
        return dict(self.runtime_value)


class FakeStrategicPlanner:
    def select_opportunity(
        self,
        selected_goal: dict,
        opportunities: list[dict],
        **_: object,
    ) -> dict | None:
        allowed = set(selected_goal.get("opportunity_ids", []))
        values = [
            dict(item)
            for item in opportunities
            if item.get("opportunity_id") in allowed
        ]
        values.sort(
            key=lambda item: float(item.get("final_score", 0.0)),
            reverse=True,
        )
        return values[0] if values else None


class FakeStrategicDevelopment:
    def __init__(self, goals: list[dict], opportunities: list[dict]) -> None:
        self.store = FakeGoalStore(goals)
        self.project_intelligence = FakeProjectIntelligence(opportunities)
        self.planner = FakeStrategicPlanner()
        self.refresh_calls = 0

    def refresh(self) -> dict:
        self.refresh_calls += 1
        return {"success": True, "status": "REFRESHED"}


class FakeExecutionStore:
    def __init__(self, records: list[dict]) -> None:
        self.records = list(records)

    def list_records(self, *, limit: int = 10000) -> list[dict]:
        return [dict(item) for item in self.records[:limit]]

    def summary(self) -> dict:
        states = [str(item.get("status", "")).upper() for item in self.records]
        return {
            "total": len(states),
            "active": sum(state == "RUNNING" for state in states),
            "completed": states.count("COMPLETED"),
            "deferred": states.count("DEFERRED_CONSTRAINTS"),
            "failed": states.count("FAILED"),
            "waiting_approval": states.count("WAITING_APPROVAL"),
        }


class FakeStrategicExecution:
    def __init__(
        self,
        development: FakeStrategicDevelopment,
        records: list[dict],
    ) -> None:
        self.strategic_development = development
        self.store = FakeExecutionStore(records)
        self.reconcile_calls = 0
        self.start_calls = 0

    def reconcile(self, *, refresh_roadmap: bool = False) -> dict:
        self.reconcile_calls += 1
        return {"success": True, "status": "RECONCILED"}

    def start(self) -> dict:
        self.start_calls += 1
        return {"success": True, "status": "STARTED"}


class DummyThread:
    def __init__(self, *, target: object, name: str, daemon: bool) -> None:
        self.target = target
        self.name = name
        self.daemon = daemon
        self.alive = False

    def start(self) -> None:
        self.alive = True

    def is_alive(self) -> bool:
        return self.alive

    def join(self, timeout: float | None = None) -> None:
        self.alive = False


class B59ModelsStoreTests(unittest.TestCase):
    def test_policy_bounds_and_never_auto_approves(self) -> None:
        policy = StrategicPortfolioPolicy.from_dict({
            "rebalance_interval_seconds": 1,
            "max_entries": 9999,
            "max_active_goals": 9,
            "cooldown_seconds": 1,
            "auto_approve": True,
        }).to_dict()
        self.assertEqual(policy["rebalance_interval_seconds"], 60.0)
        self.assertEqual(policy["max_entries"], 1000)
        self.assertEqual(policy["max_active_goals"], 1)
        self.assertEqual(policy["cooldown_seconds"], 60.0)
        self.assertFalse(policy["auto_approve"])

    def test_entry_roundtrip_normalizes_values(self) -> None:
        item = StrategicPortfolioEntry.from_dict({
            "goal_id": " g1 ",
            "subsystem": " app/ai ",
            "issue_type": "long_function",
            "status": "ready",
            "confidence": 5,
            "failed_count": -2,
        })
        self.assertEqual(item.goal_id, "g1")
        self.assertEqual(item.issue_type, "LONG_FUNCTION")
        self.assertEqual(item.status, "READY")
        self.assertEqual(item.confidence, 1.0)
        self.assertEqual(item.failed_count, 0)

    def test_store_persists_entries_and_policy(self) -> None:
        with TemporaryDirectory() as directory:
            store = StrategicPortfolioStore(directory)
            store.save_entry(StrategicPortfolioEntry(
                goal_id="g1",
                subsystem="app/ai",
                issue_type="LONG_FUNCTION",
                adaptive_priority_score=55,
            ))
            store.update_policy({"auto_approve": True, "max_active_goals": 8})
            restored = StrategicPortfolioStore(directory)
            self.assertEqual(restored.get_entry("g1")["goal_id"], "g1")
            self.assertFalse(restored.policy()["auto_approve"])
            self.assertEqual(restored.policy()["max_active_goals"], 1)

    def test_store_summary_counts_states(self) -> None:
        with TemporaryDirectory() as directory:
            store = StrategicPortfolioStore(directory)
            for index, state in enumerate(("READY", "COOLDOWN", "BLOCKED")):
                store.save_entry(StrategicPortfolioEntry(
                    goal_id=f"g{index}",
                    subsystem="app/ai",
                    issue_type="TEST",
                    status=state,
                ))
            summary = store.summary()
            self.assertEqual(summary["total"], 3)
            self.assertEqual(summary["ready"], 1)
            self.assertEqual(summary["cooldown"], 1)
            self.assertEqual(summary["blocked"], 1)

    def test_store_history_is_bounded(self) -> None:
        with TemporaryDirectory() as directory:
            store = StrategicPortfolioStore(directory, max_history=100)
            for index in range(110):
                store.record_history({"status": f"S{index}", "success": True})
            self.assertEqual(len(store.load()["history"]), 100)


class B59OptimizerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.optimizer = StrategicPortfolioOptimizer()
        self.policy = StrategicPortfolioPolicy().to_dict()

    def build(
        self,
        selected_goal: dict,
        records: list[dict] | None = None,
        *,
        existing: dict[str, dict] | None = None,
        last_subsystem: str = "",
    ) -> dict:
        return self.optimizer.build_entries(
            [selected_goal],
            list(records or []),
            existing_by_goal_id=existing or {},
            policy=self.policy,
            last_selected_subsystem=last_subsystem,
            now=NOW,
        )[0].to_dict()

    def test_untried_goal_gets_exploration_bonus(self) -> None:
        item = self.build(goal("g1", score=50))
        self.assertEqual(item["adaptive_priority_score"], 56.0)

    def test_completed_outcome_adds_bonus(self) -> None:
        item = self.build(goal("g1", score=50), [execution("g1", "COMPLETED", 0)])
        self.assertEqual(item["adaptive_priority_score"], 52.0)
        self.assertEqual(item["success_rate"], 1.0)

    def test_failures_penalize_and_trigger_cooldown(self) -> None:
        records = [
            execution("g1", "FAILED", 0),
            execution("g1", "FAILED", 1),
        ]
        item = self.build(goal("g1", score=50), records)
        self.assertEqual(item["status"], "COOLDOWN")
        self.assertEqual(item["consecutive_failures"], 2)
        self.assertLess(item["adaptive_priority_score"], 50)
        self.assertTrue(item["cooldown_until"])

    def test_three_deferrals_trigger_cooldown_without_failure(self) -> None:
        records = [
            execution("g1", "DEFERRED_CONSTRAINTS", 0),
            execution("g1", "DEFERRED_CONSTRAINTS", 1),
            execution("g1", "DEFERRED_CONSTRAINTS", 2),
        ]
        item = self.build(goal("g1"), records)
        self.assertEqual(item["status"], "COOLDOWN")
        self.assertEqual(item["failed_count"], 0)
        self.assertEqual(item["deferred_count"], 3)

    def test_single_deferral_is_neutral_ready_state(self) -> None:
        item = self.build(
            goal("g1"),
            [execution("g1", "DEFERRED_CONSTRAINTS", 0)],
        )
        self.assertEqual(item["status"], "READY")
        self.assertEqual(item["failed_count"], 0)
        self.assertFalse(item["cooldown_until"])

    def test_same_trigger_does_not_extend_existing_cooldown(self) -> None:
        records = [
            execution("g1", "FAILED", 0),
            execution("g1", "FAILED", 1),
        ]
        first = self.build(goal("g1"), records)
        second = self.optimizer.build_entries(
            [goal("g1")],
            records,
            existing_by_goal_id={"g1": first},
            policy=self.policy,
            now=NOW + timedelta(minutes=1),
        )[0].to_dict()
        self.assertEqual(second["cooldown_until"], first["cooldown_until"])

    def test_diversity_penalty_avoids_same_subsystem(self) -> None:
        normal = self.build(goal("g1", score=50, subsystem="app/ai"))
        repeated = self.build(
            goal("g1", score=50, subsystem="app/ai"),
            last_subsystem="app/ai",
        )
        self.assertEqual(
            normal["adaptive_priority_score"]
            - repeated["adaptive_priority_score"],
            self.policy["diversity_penalty"],
        )

    def test_active_and_waiting_approval_states_are_preserved(self) -> None:
        active = self.build(goal("g1"), [execution("g1", "RUNNING", 0)])
        waiting = self.build(
            goal("g1"),
            [execution("g1", "WAITING_APPROVAL", 0)],
        )
        self.assertEqual(active["status"], "ACTIVE")
        self.assertEqual(waiting["status"], "WAITING_APPROVAL")

    def test_blocked_and_completed_goals_are_not_ready(self) -> None:
        blocked = self.build(goal("g1", status="BLOCKED"))
        completed = self.build(goal("g2", status="COMPLETED", pending=0))
        self.assertEqual(blocked["status"], "BLOCKED")
        self.assertEqual(completed["status"], "COMPLETED")

    def test_candidate_selection_orders_by_adaptive_score(self) -> None:
        candidates = self.optimizer.select_candidates([
            {"goal_id": "low", "status": "READY", "pending_count": 1, "adaptive_priority_score": 20},
            {"goal_id": "high", "status": "READY", "pending_count": 1, "adaptive_priority_score": 80},
            {"goal_id": "cool", "status": "COOLDOWN", "pending_count": 1, "adaptive_priority_score": 99},
        ], min_adaptive_score=5)
        self.assertEqual([item["goal_id"] for item in candidates], ["high", "low"])


class B59ServiceTests(unittest.TestCase):
    def make_service(
        self,
        directory: str,
        *,
        goals: list[dict] | None = None,
        records: list[dict] | None = None,
    ) -> tuple[StrategicPortfolioService, FakeStrategicDevelopment, FakeStrategicExecution]:
        selected_goals = goals or [goal("g1")]
        opportunities = [
            {
                "opportunity_id": f"opp-{item['goal_id']}",
                "status": "PENDING",
                "target": f"{item['subsystem']}/target.py",
                "final_score": float(item["priority_score"]),
                "risk_score": 20.0,
                "confidence": 0.8,
            }
            for item in selected_goals
        ]
        development = FakeStrategicDevelopment(selected_goals, opportunities)
        strategic_execution = FakeStrategicExecution(
            development,
            list(records or []),
        )
        service = StrategicPortfolioService(
            directory,
            strategic_development=development,
            strategic_execution=strategic_execution,
        )
        return service, development, strategic_execution

    def test_rebalance_creates_persistent_portfolio(self) -> None:
        with TemporaryDirectory() as directory:
            service, _, strategic_execution = self.make_service(directory)
            result = service.rebalance()
            self.assertTrue(result["success"])
            self.assertEqual(result["summary"]["total"], 1)
            self.assertEqual(result["runtime"]["cycles_completed"], 1)
            self.assertEqual(strategic_execution.reconcile_calls, 1)
            self.assertTrue(Path(result["report_path"]).exists())

    def test_recommendation_selects_best_adaptive_goal(self) -> None:
        with TemporaryDirectory() as directory:
            service, development, _ = self.make_service(
                directory,
                goals=[
                    goal("low", subsystem="app/low", score=30),
                    goal("high", subsystem="app/high", score=80),
                ],
            )
            service.store.update_runtime({"enabled": True})
            service.rebalance()
            result = service.recommend_opportunity(rebalance_if_due=False)
            self.assertEqual(result["selected"]["goal_id"], "high")
            self.assertEqual(
                result["recommendation"]["opportunity_id"],
                "opp-high",
            )
            self.assertEqual(
                development.store.runtime_value["active_goal_id"],
                "high",
            )

    def test_disabled_service_does_not_recommend(self) -> None:
        with TemporaryDirectory() as directory:
            service, _, _ = self.make_service(directory)
            result = service.recommend_opportunity()
            self.assertEqual(result["status"], "STRATEGIC_PORTFOLIO_DISABLED")
            self.assertEqual(result["recommendation"], {})

    def test_paused_service_does_not_recommend(self) -> None:
        with TemporaryDirectory() as directory:
            service, _, _ = self.make_service(directory)
            service.store.update_runtime({"enabled": True, "paused": True})
            result = service.recommend_opportunity()
            self.assertEqual(result["status"], "STRATEGIC_PORTFOLIO_PAUSED")

    def test_start_enables_b58_and_never_auto_approves(self) -> None:
        with TemporaryDirectory() as directory:
            service, _, strategic_execution = self.make_service(directory)
            with patch(
                "app.ai.software_engineer.strategic_portfolio_service.threading.Thread",
                DummyThread,
            ):
                result = service.start_background()
                self.assertTrue(result["success"])
                self.assertEqual(strategic_execution.start_calls, 1)
                self.assertTrue(service.store.runtime()["enabled"])
                self.assertFalse(service.store.policy()["auto_approve"])
                service.stop_background()

    def test_observe_execution_updates_learning_state(self) -> None:
        with TemporaryDirectory() as directory:
            record = execution("g1", "DEFERRED_CONSTRAINTS", 0)
            service, _, strategic_execution = self.make_service(
                directory,
                records=[record],
            )
            result = service.observe_execution(record)
            runtime = service.store.runtime()
            self.assertTrue(result["success"])
            self.assertEqual(runtime["last_execution_id"], record["execution_id"])
            self.assertEqual(runtime["last_outcome"], "DEFERRED_CONSTRAINTS")
            self.assertEqual(strategic_execution.reconcile_calls, 0)

    def test_status_exposes_b57_b58_and_entries(self) -> None:
        with TemporaryDirectory() as directory:
            service, _, _ = self.make_service(directory)
            service.rebalance()
            result = service.status()
            self.assertEqual(result["operation"], "strategic_portfolio")
            self.assertIn("roadmap_summary", result)
            self.assertIn("execution_summary", result)
            self.assertEqual(len(result["entries"]), 1)

    def test_policy_update_hardens_safety_values(self) -> None:
        with TemporaryDirectory() as directory:
            service, _, _ = self.make_service(directory)
            result = service.update_policy({
                "auto_approve": True,
                "max_active_goals": 10,
            })
            self.assertFalse(result["policy"]["auto_approve"])
            self.assertEqual(result["policy"]["max_active_goals"], 1)


class B59B58IntegrationTests(unittest.TestCase):
    def make_b58(self) -> StrategicExecutionService:
        service = StrategicExecutionService.__new__(StrategicExecutionService)
        service.store = MagicMock()
        service.strategic_development = MagicMock()
        return service

    def test_b58_uses_b59_recommendation_when_enabled(self) -> None:
        service = self.make_b58()
        portfolio = MagicMock()
        portfolio.is_enabled.return_value = True
        portfolio.recommend_opportunity.return_value = {
            "status": "B59",
            "selected": {"goal_id": "g1"},
        }
        service.strategic_portfolio_service = portfolio
        result = service._strategic_recommendation()
        self.assertEqual(result["status"], "B59")
        portfolio.recommend_opportunity.assert_called_once_with()
        service.strategic_development.recommend_opportunity.assert_not_called()

    def test_b58_falls_back_to_b57_when_b59_disabled(self) -> None:
        service = self.make_b58()
        portfolio = MagicMock()
        portfolio.is_enabled.return_value = False
        service.strategic_portfolio_service = portfolio
        service.strategic_development.recommend_opportunity.return_value = {
            "status": "B57"
        }
        result = service._strategic_recommendation()
        self.assertEqual(result["status"], "B57")

    def test_b58_notifies_b59_after_outcome(self) -> None:
        service = self.make_b58()
        portfolio = MagicMock()
        service.strategic_portfolio_service = portfolio
        item = {"execution_id": "exec-1", "status": "COMPLETED"}
        service._notify_strategic_portfolio(item)
        portfolio.observe_execution.assert_called_once_with(item)


class B59RoutingFormattingSafetyTests(unittest.TestCase):
    def test_router_recognizes_polish_and_english_commands(self) -> None:
        router = SoftwareEngineerStrategicPortfolioRouter()
        self.assertTrue(router.can_handle("Pokaż status portfolio strategicznego"))
        self.assertTrue(router.can_handle("Rebalance strategic portfolio"))
        self.assertFalse(router.can_handle("otwórz kalkulator"))

    def test_explicit_rebalance_overrides_stale_status_context(self) -> None:
        router = SoftwareEngineerStrategicPortfolioRouter()
        self.assertEqual(
            router._action(
                "strategic_portfolio_status",
                "przelicz portfolio strategiczne",
            ),
            "rebalance",
        )

    def test_b58_router_and_controller_gate_accept_b59(self) -> None:
        command = "Pokaż status portfolio strategicznego"
        self.assertTrue(
            SoftwareEngineerStrategicExecutionRouter.can_handle(command)
        )
        self.assertTrue(AutonomousSoftwareEngineerController.can_handle(command))

    def test_router_dispatches_status_to_b59_service(self) -> None:
        router = SoftwareEngineerStrategicPortfolioRouter()
        service = MagicMock()
        service.status.return_value = {
            "success": True,
            "status": "STRATEGIC_PORTFOLIO_STATUS",
        }
        controller = SimpleNamespace(
            _normalize=lambda value: " ".join(value.casefold().split())
        )
        with patch(
            "app.ai.software_engineer."
            "software_engineer_strategic_portfolio_router."
            "bootstrap_strategic_portfolio",
            return_value=service,
        ):
            result = router.try_handle(
                controller,
                command="Pokaż status portfolio strategicznego",
                objective="",
                context={},
            )
        self.assertEqual(result["status"], "STRATEGIC_PORTFOLIO_STATUS")
        service.status.assert_called_once_with()

    def test_status_is_read_only_but_rebalance_requires_confirmation(self) -> None:
        self.assertTrue(
            is_read_only_learning_command(
                "Pokaż status portfolio strategicznego"
            )
        )
        self.assertFalse(
            is_read_only_learning_command(
                "Przelicz portfolio strategiczne"
            )
        )

    def test_formatter_reports_safety_and_portfolio(self) -> None:
        text = format_strategic_portfolio_response({
            "status": "STRATEGIC_PORTFOLIO_STATUS",
            "runtime": {"enabled": True, "running": True, "phase": "READY"},
            "policy": StrategicPortfolioPolicy().to_dict(),
            "summary": {"total": 2, "ready": 1, "cooldown": 1},
            "roadmap_summary": {"total": 15, "pending": 13, "active": 0},
            "execution_summary": {"total": 1, "completed": 0, "deferred": 1, "failed": 0},
            "entries": [],
        })
        self.assertIn("Adaptacja strategiczna B59", text)
        self.assertIn("Portfolio B59", text)
        self.assertIn("auto-approve NIE", text)

    def test_brain_formatter_routes_b59_operation(self) -> None:
        formatter = BrainResponseFormatter()
        text = formatter._format_software_engineer_response({
            "success": True,
            "status": "STRATEGIC_PORTFOLIO_STATUS",
            "operation": "strategic_portfolio",
            "runtime": {},
            "policy": {},
            "summary": {},
        })
        self.assertIn("Adaptacja strategiczna B59", text)

    def test_brain_bootstraps_b59_and_stays_below_limit(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source = (root / "app/ai/brain.py").read_text(encoding="utf-8")
        self.assertIn("bootstrap_strategic_portfolio", source)
        self.assertIn("self.strategic_portfolio_service", source)
        self.assertLess(len(source.splitlines()), 1000)

    def test_existing_audit_line_limits_remain_satisfied(self) -> None:
        root = Path(__file__).resolve().parents[1]
        controller = root / "app/ai/software_engineer/autonomous_software_engineer.py"
        advanced = root / "app/ai/software_engineer/software_engineer_advanced_change_router.py"
        self.assertLess(len(controller.read_text(encoding="utf-8").splitlines()), 440)
        self.assertLess(len(advanced.read_text(encoding="utf-8").splitlines()), 360)


if __name__ == "__main__":
    unittest.main()
