"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations

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
from app.ai.software_engineer.software_engineer_strategic_policy_formatter import (
    format_strategic_policy_response,
)
from app.ai.software_engineer.software_engineer_strategic_policy_router import (
    SoftwareEngineerStrategicPolicyRouter,
)
from app.ai.software_engineer.strategic_policy_evolution_analyzer import (
    StrategicPolicyEvolutionAnalyzer,
)
from app.ai.software_engineer.strategic_policy_evolution_models import (
    StrategicPolicyEvolutionPolicy,
    StrategicPolicyRevision,
)
from app.ai.software_engineer.strategic_policy_evolution_service import (
    StrategicPolicyEvolutionService,
)
from app.ai.software_engineer.strategic_policy_evolution_store import (
    StrategicPolicyEvolutionStore,
)
from app.ai.software_engineer.strategic_portfolio_models import (
    StrategicPortfolioPolicy,
)
from app.gui.command_safety import is_read_only_learning_command


def record(status: str, index: int, goal_id: str = "g1") -> dict:
    return {
        "execution_id": f"exec-{index}",
        "goal_id": goal_id,
        "status": status,
        "updated_at": f"2026-07-17T20:{index:02d}:00+00:00",
        "target": "app/ai/module.py",
    }


def entry(goal_id: str = "g1", subsystem: str = "app/ai") -> dict:
    return {
        "goal_id": goal_id,
        "subsystem": subsystem,
        "status": "READY",
        "adaptive_priority_score": 70.0,
    }


class FakeExecutionStore:
    def __init__(self, records: list[dict]) -> None:
        self.records = list(records)

    def list_records(self, *, limit: int = 200) -> list[dict]:
        return [dict(item) for item in self.records[:limit]]

    def summary(self) -> dict:
        statuses = [str(item.get("status", "")).upper() for item in self.records]
        return {
            "total": len(statuses),
            "completed": statuses.count("COMPLETED"),
            "deferred": statuses.count("DEFERRED_CONSTRAINTS"),
            "failed": statuses.count("FAILED"),
        }


class FakePortfolioStore:
    def __init__(self, entries: list[dict]) -> None:
        self.entries = [dict(item) for item in entries]
        self.policy_value = StrategicPortfolioPolicy().to_dict()

    def list_entries(self, *, limit: int = 1000) -> list[dict]:
        return [dict(item) for item in self.entries[:limit]]

    def policy(self) -> dict:
        return dict(self.policy_value)

    def update_policy(self, updates: dict) -> dict:
        self.policy_value = StrategicPortfolioPolicy.from_dict({
            **self.policy_value,
            **dict(updates),
        }).to_dict()
        return dict(self.policy_value)

    def summary(self) -> dict:
        return {"total": len(self.entries), "ready": len(self.entries)}


class FakePortfolio:
    def __init__(self, records: list[dict], entries: list[dict]) -> None:
        self.store = FakePortfolioStore(entries)
        self.strategic_execution = SimpleNamespace(
            store=FakeExecutionStore(records)
        )
        self.start_calls = 0
        self.rebalance_calls = 0
        self.strategic_policy_evolution_service = None

    def start_background(self) -> dict:
        self.start_calls += 1
        return {"success": True, "status": "STARTED"}

    def rebalance(self, **_: object) -> dict:
        self.rebalance_calls += 1
        return {"success": True, "status": "REBALANCED"}


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


class B60ModelsStoreTests(unittest.TestCase):
    def test_policy_bounds_and_never_auto_approves(self) -> None:
        policy = StrategicPolicyEvolutionPolicy.from_dict({
            "learning_interval_seconds": 1,
            "observation_window": 99999,
            "min_observations": 0,
            "auto_approve": True,
        }).to_dict()
        self.assertEqual(policy["learning_interval_seconds"], 60.0)
        self.assertEqual(policy["observation_window"], 5000)
        self.assertEqual(policy["min_observations"], 1)
        self.assertFalse(policy["auto_approve"])

    def test_revision_filters_unsafe_fields(self) -> None:
        revision = StrategicPolicyRevision.from_dict({
            "policy": {"failure_penalty": 10, "auto_approve": True},
            "changes": {"failure_penalty": 10, "auto_approve": True},
        }).to_dict()
        self.assertFalse(revision["policy"]["auto_approve"])
        self.assertNotIn("auto_approve", revision["changes"])

    def test_store_persists_revision_and_policy(self) -> None:
        with TemporaryDirectory() as directory:
            store = StrategicPolicyEvolutionStore(directory)
            saved = store.save_revision(StrategicPolicyRevision(
                policy=StrategicPortfolioPolicy().to_dict(),
                status="ACTIVE",
            ))
            store.update_runtime({"active_revision_id": saved["revision_id"]})
            store.update_policy({"auto_approve": True})
            restored = StrategicPolicyEvolutionStore(directory)
            self.assertEqual(
                restored.active_revision()["revision_id"], saved["revision_id"]
            )
            self.assertFalse(restored.policy()["auto_approve"])

    def test_observed_execution_ids_are_deduplicated(self) -> None:
        with TemporaryDirectory() as directory:
            store = StrategicPolicyEvolutionStore(directory)
            self.assertTrue(store.mark_observed("exec-1"))
            self.assertFalse(store.mark_observed("exec-1"))
            self.assertEqual(store.summary()["observed_executions"], 1)

    def test_store_history_is_bounded_and_readable(self) -> None:
        with TemporaryDirectory() as directory:
            store = StrategicPolicyEvolutionStore(directory, max_history=100)
            for index in range(120):
                store.record_history({"status": f"S{index}", "success": True})
            self.assertEqual(len(store.history(limit=200)), 100)


class B60AnalyzerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.analyzer = StrategicPolicyEvolutionAnalyzer()
        self.policy = StrategicPortfolioPolicy().to_dict()
        self.evolution = StrategicPolicyEvolutionPolicy().to_dict()

    def test_insufficient_evidence_holds_policy(self) -> None:
        result = self.analyzer.analyze(
            [record("DEFERRED_CONSTRAINTS", 1)],
            [entry()],
            current_policy=self.policy,
            evolution_policy=self.evolution,
        )
        self.assertEqual(result["decision"], "HOLD")
        self.assertEqual(result["changes"], {})

    def test_failures_increase_protection(self) -> None:
        records = [record("FAILED", index) for index in range(4)]
        result = self.analyzer.analyze(
            records, [entry()], current_policy=self.policy,
            evolution_policy=self.evolution,
        )
        self.assertEqual(result["decision"], "PROPOSE")
        self.assertGreater(
            result["changes"]["failure_penalty"],
            self.policy["failure_penalty"],
        )
        self.assertFalse(result["proposed_policy"]["auto_approve"])

    def test_deferred_outcomes_increase_exploration(self) -> None:
        records = [record("DEFERRED_CONSTRAINTS", index) for index in range(4)]
        result = self.analyzer.analyze(
            records, [entry()], current_policy=self.policy,
            evolution_policy=self.evolution,
        )
        self.assertGreater(
            result["changes"]["exploration_bonus"],
            self.policy["exploration_bonus"],
        )

    def test_successes_reward_completion(self) -> None:
        records = [record("COMPLETED", index) for index in range(5)]
        result = self.analyzer.analyze(
            records, [entry()], current_policy=self.policy,
            evolution_policy=self.evolution,
        )
        self.assertGreater(
            result["changes"]["completion_bonus"],
            self.policy["completion_bonus"],
        )

    def test_concentration_increases_diversity_penalty(self) -> None:
        records = [record("COMPLETED", index, "g1") for index in range(4)]
        result = self.analyzer.analyze(
            records, [entry("g1", "app/ai")],
            current_policy=self.policy,
            evolution_policy=self.evolution,
        )
        self.assertGreater(
            result["changes"]["diversity_penalty"],
            self.policy["diversity_penalty"],
        )

    def test_metrics_count_terminal_outcomes(self) -> None:
        result = self.analyzer.analyze(
            [
                record("COMPLETED", 1),
                record("FAILED", 2),
                record("DEFERRED_CONSTRAINTS", 3),
            ],
            [entry()],
            current_policy=self.policy,
            evolution_policy={**self.evolution, "min_observations": 1},
        )
        self.assertEqual(result["metrics"]["observations"], 3)
        self.assertEqual(result["metrics"]["completed"], 1)
        self.assertEqual(result["metrics"]["failed"], 1)
        self.assertEqual(result["metrics"]["deferred"], 1)


class B60ServiceTests(unittest.TestCase):
    def make_service(
        self,
        directory: str,
        records: list[dict] | None = None,
        entries: list[dict] | None = None,
    ) -> tuple[StrategicPolicyEvolutionService, FakePortfolio]:
        portfolio = FakePortfolio(records or [], entries or [entry()])
        service = StrategicPolicyEvolutionService(
            directory,
            strategic_portfolio=portfolio,
        )
        return service, portfolio

    def test_learn_creates_baseline_and_holds_with_low_evidence(self) -> None:
        with TemporaryDirectory() as directory:
            service, _ = self.make_service(
                directory, [record("DEFERRED_CONSTRAINTS", 1)]
            )
            result = service.learn()
            self.assertEqual(result["status"], "STRATEGIC_POLICY_EVOLUTION_HOLD")
            self.assertIsNotNone(service.store.active_revision())
            self.assertEqual(service.store.runtime()["cycles_completed"], 1)

    def test_learn_auto_applies_safe_proposal(self) -> None:
        with TemporaryDirectory() as directory:
            service, portfolio = self.make_service(
                directory,
                [record("FAILED", index) for index in range(4)],
            )
            result = service.learn()
            self.assertEqual(result["status"], "STRATEGIC_POLICY_EVOLUTION_APPLIED")
            self.assertGreater(portfolio.store.policy()["failure_penalty"], 8.0)
            self.assertFalse(portfolio.store.policy()["auto_approve"])
            self.assertEqual(portfolio.rebalance_calls, 1)

    def test_same_evidence_does_not_reapply_policy(self) -> None:
        with TemporaryDirectory() as directory:
            service, portfolio = self.make_service(
                directory,
                [record("FAILED", index) for index in range(4)],
            )
            first = service.learn()
            penalty = portfolio.store.policy()["failure_penalty"]
            second = service.learn()
            self.assertEqual(first["status"], "STRATEGIC_POLICY_EVOLUTION_APPLIED")
            self.assertEqual(second["status"], "STRATEGIC_POLICY_NO_NEW_EVIDENCE")
            self.assertEqual(portfolio.store.policy()["failure_penalty"], penalty)
            self.assertEqual(portfolio.rebalance_calls, 1)

    def test_manual_proposal_then_apply(self) -> None:
        with TemporaryDirectory() as directory:
            service, portfolio = self.make_service(
                directory,
                [record("FAILED", index) for index in range(4)],
            )
            service.store.update_policy({"auto_apply_safe_changes": False})
            proposed = service.learn()
            self.assertEqual(proposed["status"], "STRATEGIC_POLICY_PROPOSAL_READY")
            applied = service.apply_proposal()
            self.assertTrue(applied["success"])
            self.assertGreater(portfolio.store.policy()["failure_penalty"], 8.0)

    def test_empty_apply_is_rejected(self) -> None:
        with TemporaryDirectory() as directory:
            service, _ = self.make_service(directory)
            result = service.apply_proposal()
            self.assertEqual(result["status"], "STRATEGIC_POLICY_NO_PROPOSAL")

    def test_rollback_restores_previous_policy(self) -> None:
        with TemporaryDirectory() as directory:
            service, portfolio = self.make_service(
                directory,
                [record("FAILED", index) for index in range(4)],
            )
            original = portfolio.store.policy()["failure_penalty"]
            service.learn()
            self.assertGreater(portfolio.store.policy()["failure_penalty"], original)
            result = service.rollback()
            self.assertTrue(result["success"])
            self.assertEqual(portfolio.store.policy()["failure_penalty"], original)

    def test_observe_execution_is_idempotent(self) -> None:
        with TemporaryDirectory() as directory:
            service, _ = self.make_service(directory)
            item = record("COMPLETED", 1)
            first = service.observe_execution(item)
            second = service.observe_execution(item)
            self.assertTrue(first["success"])
            self.assertEqual(
                second["status"], "STRATEGIC_POLICY_EXECUTION_ALREADY_OBSERVED"
            )

    def test_disabled_observer_records_without_learning(self) -> None:
        with TemporaryDirectory() as directory:
            service, _ = self.make_service(directory)
            result = service.observe_execution(record("COMPLETED", 1))
            self.assertEqual(result["status"], "STRATEGIC_POLICY_EXECUTION_OBSERVED")
            self.assertEqual(service.store.runtime()["cycles_completed"], 0)

    def test_start_enables_b59_and_never_auto_approves(self) -> None:
        with TemporaryDirectory() as directory:
            service, portfolio = self.make_service(directory)
            with patch(
                "app.ai.software_engineer.strategic_policy_evolution_service.threading.Thread",
                DummyThread,
            ):
                result = service.start_background()
                self.assertTrue(result["success"])
                self.assertEqual(portfolio.start_calls, 1)
                self.assertFalse(service.store.policy()["auto_approve"])
                service.stop_background()

    def test_status_exposes_policy_metrics_and_revisions(self) -> None:
        with TemporaryDirectory() as directory:
            service, _ = self.make_service(directory)
            service.learn()
            result = service.status()
            self.assertEqual(result["operation"], "strategic_policy_evolution")
            self.assertIn("current_portfolio_policy", result)
            self.assertTrue(result["revisions"])

    def test_update_policy_hardens_auto_approve(self) -> None:
        with TemporaryDirectory() as directory:
            service, _ = self.make_service(directory)
            result = service.update_policy({"auto_approve": True})
            self.assertFalse(result["policy"]["auto_approve"])


class B60IntegrationRoutingFormattingTests(unittest.TestCase):
    def test_b59_observer_notifies_b60(self) -> None:
        from app.ai.software_engineer.strategic_portfolio_service import (
            StrategicPortfolioService,
        )
        service = StrategicPortfolioService.__new__(StrategicPortfolioService)
        service.store = MagicMock()
        service.rebalance = MagicMock(return_value={"success": True})
        learner = MagicMock()
        service.strategic_policy_evolution_service = learner
        item = record("COMPLETED", 1)
        service.observe_execution(item)
        learner.observe_execution.assert_called_once_with(item)

    def test_router_recognizes_polish_and_english_commands(self) -> None:
        router = SoftwareEngineerStrategicPolicyRouter()
        self.assertTrue(router.can_handle("Pokaż status samouczenia strategicznego"))
        self.assertTrue(router.can_handle("Run strategic policy learning cycle"))
        self.assertFalse(router.can_handle("otwórz kalkulator"))

    def test_explicit_learn_overrides_stale_status_context(self) -> None:
        router = SoftwareEngineerStrategicPolicyRouter()
        self.assertEqual(
            router._action(
                "strategic_policy_status",
                "wykonaj cykl samouczenia strategicznego",
            ),
            "learn",
        )

    def test_router_dispatches_status_to_service(self) -> None:
        router = SoftwareEngineerStrategicPolicyRouter()
        service = MagicMock()
        service.status.return_value = {
            "success": True,
            "status": "STRATEGIC_POLICY_EVOLUTION_STATUS",
        }
        controller = SimpleNamespace(
            _normalize=lambda value: " ".join(value.casefold().split())
        )
        with patch(
            "app.ai.software_engineer.software_engineer_strategic_policy_router."
            "bootstrap_strategic_policy_evolution",
            return_value=service,
        ):
            result = router.try_handle(
                controller,
                command="Pokaż status samouczenia strategicznego",
                objective="",
                context={},
            )
        self.assertEqual(result["status"], "STRATEGIC_POLICY_EVOLUTION_STATUS")
        service.status.assert_called_once_with()

    def test_controller_gate_accepts_b60_through_router_chain(self) -> None:
        command = "Pokaż status samouczenia strategicznego"
        self.assertTrue(SoftwareEngineerStrategicExecutionRouter.can_handle(command))
        self.assertTrue(AutonomousSoftwareEngineerController.can_handle(command))

    def test_status_is_read_only_but_learning_requires_confirmation(self) -> None:
        self.assertTrue(
            is_read_only_learning_command("Pokaż status samouczenia strategicznego")
        )
        self.assertFalse(
            is_read_only_learning_command("Wykonaj cykl samouczenia strategicznego")
        )

    def test_formatter_reports_safety_and_learning(self) -> None:
        text = format_strategic_policy_response({
            "status": "STRATEGIC_POLICY_EVOLUTION_STATUS",
            "runtime": {"enabled": True, "phase": "READY", "cycles_completed": 2},
            "policy": StrategicPolicyEvolutionPolicy().to_dict(),
            "summary": {"revisions": 1, "active": 1, "proposed": 0},
            "current_portfolio_policy": StrategicPortfolioPolicy().to_dict(),
        })
        self.assertIn("Samouczenie strategiczne B60", text)
        self.assertIn("auto-approve NIE", text)

    def test_brain_formatter_routes_b60_operation(self) -> None:
        formatter = BrainResponseFormatter()
        text = formatter._format_software_engineer_response({
            "success": True,
            "status": "STRATEGIC_POLICY_EVOLUTION_STATUS",
            "operation": "strategic_policy_evolution",
            "runtime": {},
            "policy": {},
            "summary": {},
        })
        self.assertIn("Samouczenie strategiczne B60", text)

    def test_brain_bootstraps_b60_and_stays_below_limit(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source = (root / "app/ai/brain.py").read_text(encoding="utf-8")
        self.assertIn("bootstrap_strategic_policy_evolution", source)
        self.assertIn("self.strategic_policy_evolution_service", source)
        self.assertLess(len(source.splitlines()), 1000)

    def test_existing_audit_limits_remain_satisfied(self) -> None:
        root = Path(__file__).resolve().parents[1]
        controller = root / "app/ai/software_engineer/autonomous_software_engineer.py"
        advanced = root / "app/ai/software_engineer/software_engineer_advanced_change_router.py"
        service = root / "app/ai/software_engineer/strategic_policy_evolution_service.py"
        self.assertLess(len(controller.read_text(encoding="utf-8").splitlines()), 440)
        self.assertLess(len(advanced.read_text(encoding="utf-8").splitlines()), 360)
        self.assertLess(len(service.read_text(encoding="utf-8").splitlines()), 800)


if __name__ == "__main__":
    unittest.main()
