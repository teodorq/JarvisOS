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
from app.ai.software_engineer.software_engineer_strategic_validation_formatter import (
    format_strategic_validation_response,
)
from app.ai.software_engineer.software_engineer_strategic_validation_router import (
    SoftwareEngineerStrategicValidationRouter,
)
from app.ai.software_engineer.strategic_policy_evolution_models import (
    StrategicPolicyRevision,
)
from app.ai.software_engineer.strategic_policy_validation_analyzer import (
    StrategicPolicyValidationAnalyzer,
)
from app.ai.software_engineer.strategic_policy_validation_models import (
    StrategicPolicyExperiment,
    StrategicPolicyValidationPolicy,
)
from app.ai.software_engineer.strategic_policy_validation_service import (
    StrategicPolicyValidationService,
)
from app.ai.software_engineer.strategic_policy_validation_store import (
    StrategicPolicyValidationStore,
)
from app.ai.software_engineer.strategic_portfolio_models import (
    StrategicPortfolioPolicy,
)
from app.gui.command_safety import is_read_only_learning_command


def execution(index: int, status: str, goal_id: str = "g1") -> dict:
    return {
        "execution_id": f"exec-{index}",
        "goal_id": goal_id,
        "status": status,
        "updated_at": f"2026-07-18T00:{index:02d}:00+00:00",
    }


def portfolio_entry(
    goal_id: str,
    *,
    base: float,
    completed: int = 0,
    failed: int = 0,
    deferred: int = 0,
    pending: int = 1,
) -> dict:
    total = completed + failed + deferred
    return {
        "goal_id": goal_id,
        "status": "READY",
        "base_priority_score": base,
        "adaptive_priority_score": base,
        "value_score": base,
        "risk_score": 20.0,
        "confidence": 0.8,
        "pending_count": pending,
        "executions_total": total,
        "completed_count": completed,
        "failed_count": failed,
        "deferred_count": deferred,
    }


class FakeExecutionStore:
    def __init__(self, records: list[dict]) -> None:
        self.records = [dict(item) for item in records]

    def list_records(self, *, limit: int = 500) -> list[dict]:
        return [dict(item) for item in self.records[:limit]]

    def summary(self) -> dict:
        return {"total": len(self.records)}


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
            **self.policy_value, **dict(updates)
        }).to_dict()
        return dict(self.policy_value)

    def summary(self) -> dict:
        return {"total": len(self.entries)}


class FakeEvolutionStore:
    def __init__(self, proposal: dict | None, policy: dict) -> None:
        self.revisions: dict[str, dict] = {}
        self.runtime_value = {
            "proposed_revision_id": "",
            "active_revision_id": "active-1",
        }
        self.policy_value = {
            "auto_apply_safe_changes": True,
            "auto_approve": False,
        }
        active = StrategicPolicyRevision(
            revision_id="active-1",
            policy=policy,
            status="ACTIVE",
        ).to_dict()
        self.revisions["active-1"] = active
        if proposal:
            self.revisions[proposal["revision_id"]] = dict(proposal)
            self.runtime_value["proposed_revision_id"] = proposal["revision_id"]

    def active_revision(self) -> dict:
        return dict(self.revisions["active-1"])

    def get_revision(self, revision_id: str) -> dict | None:
        item = self.revisions.get(revision_id)
        return dict(item) if item else None

    def save_revision(self, revision: dict) -> dict:
        self.revisions[revision["revision_id"]] = dict(revision)
        return dict(revision)

    def runtime(self) -> dict:
        return dict(self.runtime_value)

    def update_runtime(self, updates: dict) -> dict:
        self.runtime_value.update(dict(updates))
        return dict(self.runtime_value)

    def policy(self) -> dict:
        return dict(self.policy_value)

    def update_policy(self, updates: dict) -> dict:
        self.policy_value.update(dict(updates))
        self.policy_value["auto_approve"] = False
        return dict(self.policy_value)

    def summary(self) -> dict:
        return {"revisions": len(self.revisions)}


class FakeEvolution:
    def __init__(self, entries: list[dict], records: list[dict], proposal: dict | None):
        self.strategic_portfolio = SimpleNamespace(
            store=FakePortfolioStore(entries),
            start_background=MagicMock(return_value={"success": True}),
        )
        self.strategic_execution = SimpleNamespace(
            store=FakeExecutionStore(records)
        )
        self.strategic_portfolio.strategic_execution = self.strategic_execution
        self.store = FakeEvolutionStore(
            proposal,
            self.strategic_portfolio.store.policy(),
        )
        self.learn = MagicMock(return_value={
            "success": True,
            "status": "STRATEGIC_POLICY_PROPOSAL_READY" if proposal else "HOLD",
        })
        self.start_background = MagicMock(return_value={"success": True})
        self.apply_proposal = MagicMock(side_effect=self._apply)
        self.strategic_policy_validation_service = None

    def _apply(self, revision_id: str) -> dict:
        revision = self.store.get_revision(revision_id)
        if not revision or revision.get("status") != "PROPOSED":
            return {"success": False, "errors": ["missing"]}
        revision["status"] = "ACTIVE"
        self.store.save_revision(revision)
        self.store.runtime_value["proposed_revision_id"] = ""
        self.strategic_portfolio.store.update_policy(revision.get("changes", {}))
        return {"success": True, "revision": revision}


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


class B61ModelsStoreTests(unittest.TestCase):
    def test_policy_bounds_and_never_auto_approves(self) -> None:
        policy = StrategicPolicyValidationPolicy.from_dict({
            "validation_interval_seconds": 1,
            "min_observations": 0,
            "top_k": 999,
            "auto_approve": True,
        }).to_dict()
        self.assertEqual(policy["validation_interval_seconds"], 60.0)
        self.assertEqual(policy["min_observations"], 1)
        self.assertEqual(policy["top_k"], 20)
        self.assertFalse(policy["auto_approve"])

    def test_experiment_hardens_candidate_policy(self) -> None:
        item = StrategicPolicyExperiment.from_dict({
            "revision_id": "r1",
            "baseline_revision_id": "r0",
            "candidate_policy": {"auto_approve": True, "max_active_goals": 9},
            "baseline_policy": {"auto_approve": True},
        }).to_dict()
        self.assertFalse(item["candidate_policy"]["auto_approve"])
        self.assertEqual(item["candidate_policy"]["max_active_goals"], 1)

    def test_store_persists_experiment_and_policy(self) -> None:
        with TemporaryDirectory() as directory:
            store = StrategicPolicyValidationStore(directory)
            saved = store.save_experiment(StrategicPolicyExperiment(
                revision_id="r1",
                baseline_revision_id="r0",
                candidate_policy={},
                baseline_policy={},
                status="PASSED",
            ))
            store.update_runtime({"last_experiment_id": saved["experiment_id"]})
            store.update_policy({"auto_approve": True})
            restored = StrategicPolicyValidationStore(directory)
            self.assertEqual(
                restored.get_experiment(saved["experiment_id"])["status"],
                "PASSED",
            )
            self.assertFalse(restored.policy()["auto_approve"])

    def test_store_deduplicates_lookup_by_revision_and_signature(self) -> None:
        with TemporaryDirectory() as directory:
            store = StrategicPolicyValidationStore(directory)
            saved = store.save_experiment(StrategicPolicyExperiment(
                revision_id="r1",
                baseline_revision_id="r0",
                candidate_policy={},
                baseline_policy={},
                evidence_signature="abc",
            ))
            found = store.latest_for_revision("r1", "abc")
            self.assertEqual(found["experiment_id"], saved["experiment_id"])

    def test_store_history_is_bounded(self) -> None:
        with TemporaryDirectory() as directory:
            store = StrategicPolicyValidationStore(directory, max_history=100)
            for index in range(120):
                store.record_history({"status": f"S{index}", "success": True})
            self.assertEqual(len(store.history(limit=200)), 100)


class B61AnalyzerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.analyzer = StrategicPolicyValidationAnalyzer()
        self.baseline = StrategicPortfolioPolicy().to_dict()
        self.validation = StrategicPolicyValidationPolicy().to_dict()

    def test_insufficient_evidence_holds(self) -> None:
        result = self.analyzer.analyze(
            [portfolio_entry("g1", base=80)],
            [execution(1, "DEFERRED_CONSTRAINTS")],
            baseline_policy=self.baseline,
            candidate_policy=self.baseline,
            changes={},
            validation_policy=self.validation,
        )
        self.assertEqual(result["decision"], "HOLD")
        self.assertFalse(result["checks"]["enough_evidence"])

    def test_unsafe_field_rejects(self) -> None:
        result = self.analyzer.analyze(
            [portfolio_entry("g1", base=80, completed=3)],
            [execution(i, "COMPLETED") for i in range(3)],
            baseline_policy=self.baseline,
            candidate_policy={**self.baseline, "auto_approve": True},
            changes={"auto_approve": True},
            validation_policy=self.validation,
        )
        self.assertEqual(result["decision"], "REJECT")
        self.assertFalse(result["checks"]["hard_safety"])

    def test_safe_non_regressing_policy_passes(self) -> None:
        entries = [
            portfolio_entry("good", base=80, completed=4),
            portfolio_entry("bad", base=90, failed=2),
        ]
        candidate = {**self.baseline, "failure_penalty": 12.0}
        result = self.analyzer.analyze(
            entries,
            [execution(i, "COMPLETED", "good") for i in range(4)]
            + [execution(10 + i, "FAILED", "bad") for i in range(2)],
            baseline_policy=self.baseline,
            candidate_policy=candidate,
            changes={"failure_penalty": 12.0},
            validation_policy={**self.validation, "top_k": 1},
        )
        self.assertEqual(result["decision"], "PASS")
        self.assertTrue(result["checks"]["failure_exposure_safe"])

    def test_candidate_exposing_failed_goal_rejects(self) -> None:
        entries = [
            portfolio_entry("good", base=80, completed=4),
            portfolio_entry("bad", base=95, failed=3),
        ]
        candidate = {**self.baseline, "failure_penalty": 0.0}
        result = self.analyzer.analyze(
            entries,
            [execution(i, "COMPLETED", "good") for i in range(4)]
            + [execution(10 + i, "FAILED", "bad") for i in range(3)],
            baseline_policy=self.baseline,
            candidate_policy=candidate,
            changes={"failure_penalty": 0.0},
            validation_policy={**self.validation, "top_k": 1},
        )
        self.assertEqual(result["decision"], "REJECT")

    def test_replay_signature_is_stable(self) -> None:
        records = [execution(1, "COMPLETED")]
        self.assertEqual(
            self.analyzer.evidence_signature(records),
            self.analyzer.evidence_signature(records),
        )


class B61ServiceTests(unittest.TestCase):
    def make_service(
        self,
        directory: str,
        *,
        proposal: dict | None,
        records: list[dict],
        entries: list[dict],
    ) -> tuple[StrategicPolicyValidationService, FakeEvolution]:
        evolution = FakeEvolution(entries, records, proposal)
        service = StrategicPolicyValidationService(
            directory,
            strategic_policy_evolution=evolution,
        )
        evolution.strategic_policy_validation_service = service
        return service, evolution

    def proposal(self, changes: dict) -> dict:
        baseline = StrategicPortfolioPolicy().to_dict()
        return StrategicPolicyRevision(
            revision_id="proposal-1",
            policy={**baseline, **changes},
            changes=changes,
            status="PROPOSED",
            confidence=0.9,
            evidence_count=6,
        ).to_dict()

    def test_validate_holds_with_low_evidence(self) -> None:
        with TemporaryDirectory() as directory:
            service, _ = self.make_service(
                directory,
                proposal=self.proposal({"failure_penalty": 9.0}),
                records=[execution(1, "FAILED")],
                entries=[portfolio_entry("g1", base=80, failed=1)],
            )
            result = service.validate()
            self.assertEqual(
                result["status"],
                "STRATEGIC_POLICY_VALIDATION_INSUFFICIENT_EVIDENCE",
            )

    def test_validate_passes_safe_candidate(self) -> None:
        with TemporaryDirectory() as directory:
            service, _ = self.make_service(
                directory,
                proposal=self.proposal({"failure_penalty": 12.0}),
                records=[execution(i, "COMPLETED", "good") for i in range(4)]
                + [execution(10 + i, "FAILED", "bad") for i in range(2)],
                entries=[
                    portfolio_entry("good", base=80, completed=4),
                    portfolio_entry("bad", base=90, failed=2),
                ],
            )
            service.store.update_policy({"top_k": 1})
            result = service.validate()
            self.assertEqual(result["status"], "STRATEGIC_POLICY_VALIDATION_PASSED")

    def test_duplicate_validation_returns_existing_experiment(self) -> None:
        with TemporaryDirectory() as directory:
            service, _ = self.make_service(
                directory,
                proposal=self.proposal({"failure_penalty": 12.0}),
                records=[execution(i, "COMPLETED", "good") for i in range(4)]
                + [execution(10 + i, "FAILED", "bad") for i in range(2)],
                entries=[
                    portfolio_entry("good", base=80, completed=4),
                    portfolio_entry("bad", base=90, failed=2),
                ],
            )
            service.store.update_policy({"top_k": 1})
            service.validate()
            second = service.validate()
            self.assertEqual(
                second["status"],
                "STRATEGIC_POLICY_VALIDATION_ALREADY_RECORDED",
            )
            self.assertEqual(service.store.summary()["experiments"], 1)

    def test_promote_requires_passed_experiment(self) -> None:
        with TemporaryDirectory() as directory:
            service, _ = self.make_service(
                directory,
                proposal=self.proposal({"failure_penalty": 9.0}),
                records=[execution(1, "FAILED")],
                entries=[portfolio_entry("g1", base=80, failed=1)],
            )
            self.assertFalse(service.promote()["success"])

    def test_promote_applies_b60_revision(self) -> None:
        with TemporaryDirectory() as directory:
            service, evolution = self.make_service(
                directory,
                proposal=self.proposal({"failure_penalty": 12.0}),
                records=[execution(i, "COMPLETED", "good") for i in range(4)]
                + [execution(10 + i, "FAILED", "bad") for i in range(2)],
                entries=[
                    portfolio_entry("good", base=80, completed=4),
                    portfolio_entry("bad", base=90, failed=2),
                ],
            )
            service.store.update_policy({"top_k": 1})
            validated = service.validate()
            result = service.promote(validated["experiment"]["experiment_id"])
            self.assertTrue(result["success"])
            evolution.apply_proposal.assert_called_once_with("proposal-1")
            self.assertEqual(result["experiment"]["status"], "PROMOTED")

    def test_reject_quarantines_proposal(self) -> None:
        with TemporaryDirectory() as directory:
            service, evolution = self.make_service(
                directory,
                proposal=self.proposal({"failure_penalty": 9.0}),
                records=[execution(1, "FAILED")],
                entries=[portfolio_entry("g1", base=80, failed=1)],
            )
            result = service.reject()
            self.assertTrue(result["success"])
            self.assertEqual(
                evolution.store.get_revision("proposal-1")["status"],
                "REJECTED",
            )
            self.assertEqual(evolution.store.runtime()["proposed_revision_id"], "")

    def test_run_cycle_disables_direct_b60_auto_apply(self) -> None:
        with TemporaryDirectory() as directory:
            service, evolution = self.make_service(
                directory,
                proposal=None,
                records=[],
                entries=[],
            )
            result = service.run_cycle()
            self.assertTrue(result["success"])
            self.assertFalse(evolution.store.policy()["auto_apply_safe_changes"])
            evolution.learn.assert_called_once_with(apply_if_safe=False)

    def test_start_enables_supervisor_and_never_auto_approves(self) -> None:
        with TemporaryDirectory() as directory:
            service, evolution = self.make_service(
                directory,
                proposal=None,
                records=[],
                entries=[],
            )
            with patch(
                "app.ai.software_engineer.strategic_policy_validation_service.threading.Thread",
                DummyThread,
            ):
                result = service.start_background()
                self.assertTrue(result["success"])
                self.assertFalse(service.store.policy()["auto_approve"])
                self.assertTrue(evolution.start_background.called)
                service.stop_background()

    def test_status_exposes_gate_and_experiments(self) -> None:
        with TemporaryDirectory() as directory:
            service, _ = self.make_service(
                directory,
                proposal=None,
                records=[],
                entries=[],
            )
            result = service.status()
            self.assertEqual(result["operation"], "strategic_policy_validation")
            self.assertFalse(result["b60_policy"]["auto_approve"])
            self.assertIn("experiments", result)

    def test_update_policy_never_auto_approves(self) -> None:
        with TemporaryDirectory() as directory:
            service, _ = self.make_service(
                directory,
                proposal=None,
                records=[],
                entries=[],
            )
            result = service.update_policy({"auto_approve": True})
            self.assertFalse(result["policy"]["auto_approve"])


class B61RoutingFormattingTests(unittest.TestCase):
    def test_router_recognizes_polish_and_english(self) -> None:
        router = SoftwareEngineerStrategicValidationRouter()
        self.assertTrue(router.can_handle(
            "Pokaż status walidacji polityki strategicznej"
        ))
        self.assertTrue(router.can_handle(
            "Run strategic policy validation cycle"
        ))
        self.assertFalse(router.can_handle("otwórz kalkulator"))

    def test_controller_gate_recognizes_b61(self) -> None:
        self.assertTrue(AutonomousSoftwareEngineerController.can_handle(
            "Przeprowadź cykl walidacji polityki strategicznej"
        ))

    def test_read_only_status_does_not_require_confirmation(self) -> None:
        self.assertTrue(is_read_only_learning_command(
            "Pokaż status walidacji polityki strategicznej"
        ))
        self.assertFalse(is_read_only_learning_command(
            "Promuj zwalidowaną politykę strategiczną"
        ))

    def test_explicit_cycle_overrides_stale_status_context(self) -> None:
        router = SoftwareEngineerStrategicValidationRouter()
        self.assertEqual(
            router._action(
                "strategic_validation_status",
                "przeprowadź cykl walidacji polityki strategicznej",
            ),
            "cycle",
        )

    def test_router_dispatches_cycle(self) -> None:
        router = SoftwareEngineerStrategicValidationRouter()
        service = MagicMock()
        service.run_cycle.return_value = {
            "success": True,
            "status": "STRATEGIC_POLICY_VALIDATION_NO_PROPOSAL",
        }
        controller = SimpleNamespace(
            _normalize=lambda value: " ".join(value.casefold().split())
        )
        with patch(
            "app.ai.software_engineer."
            "software_engineer_strategic_validation_router."
            "bootstrap_strategic_policy_validation",
            return_value=service,
        ):
            result = router.try_handle(
                controller,
                command="Przeprowadź cykl walidacji polityki strategicznej",
                objective="",
                context={"operation": "strategic_validation_status"},
            )
        self.assertEqual(
            result["status"], "STRATEGIC_POLICY_VALIDATION_NO_PROPOSAL"
        )
        service.run_cycle.assert_called_once_with()

    def test_formatter_reports_safety_and_gate(self) -> None:
        text = format_strategic_validation_response({
            "status": "STRATEGIC_POLICY_VALIDATION_PASSED",
            "runtime": {"enabled": True, "phase": "PASSED"},
            "summary": {"experiments": 1, "passed": 1},
            "metrics": {"observations": 10, "top_k_overlap": 1.0},
            "checks": {"hard_safety": True},
            "b60_policy": {"auto_apply_safe_changes": False},
            "policy": {"auto_promote_validated": True},
        })
        self.assertIn("B61", text)
        self.assertIn("auto-zastosowanie bez walidacji NIE", text)
        self.assertIn("auto-approve NIE", text)

    def test_brain_formatter_routes_b61_operation(self) -> None:
        formatter = BrainResponseFormatter()
        text = formatter._format_software_engineer_response({
            "operation": "strategic_policy_validation",
            "status": "STRATEGIC_POLICY_VALIDATION_STATUS",
            "runtime": {},
            "summary": {},
            "policy": {},
        })
        self.assertIn("B61", text)

    def test_source_limits_remain_bounded(self) -> None:
        root = Path(__file__).resolve().parents[1]
        self.assertLess(
            len((root / "app/ai/brain.py").read_text(encoding="utf-8").splitlines()),
            1000,
        )
        self.assertLess(
            len((root / "app/ai/software_engineer/autonomous_software_engineer.py")
                .read_text(encoding="utf-8").splitlines()),
            440,
        )
        self.assertLess(
            len((root / "app/ai/software_engineer/software_engineer_advanced_change_router.py")
                .read_text(encoding="utf-8").splitlines()),
            360,
        )


if __name__ == "__main__":
    unittest.main()
