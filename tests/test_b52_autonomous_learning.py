"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from app.ai.brain_response_formatter import BrainResponseFormatter
from app.ai.software_engineer.autonomous_learning_engine import (
    AutonomousLearningEngine,
)
from app.ai.software_engineer.autonomous_learning_store import (
    AutonomousLearningStore,
)
from app.ai.software_engineer.autonomy_history_collector import (
    AutonomyHistoryCollector,
)
from app.ai.software_engineer.autonomy_outcome_analyzer import (
    AutonomyOutcomeAnalyzer,
)
from app.ai.software_engineer.autonomy_policy_learner import (
    AutonomyPolicyLearner,
)
from app.ai.software_engineer.full_autonomy_workflow import (
    FullAutonomyWorkflow,
)
from app.ai.software_engineer.multi_campaign_models import (
    ManagedCampaign,
    MultiCampaignPortfolio,
)
from app.ai.software_engineer.portfolio_optimizer import (
    PortfolioOptimizer,
)
from app.ai.software_engineer.software_engineer_learning_formatter import (
    format_autonomous_learning_response,
)
from app.ai.software_engineer.software_engineer_learning_router import (
    SoftwareEngineerLearningRouter,
)


class FakeListStore:

    def __init__(self, values=None):
        self.values = list(values or [])

    def list_recent(self, *, limit=20):
        return [
            dict(item)
            for item in self.values[:limit]
        ]


class B52AutonomousLearningTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "app").mkdir()
        (self.root / "tests").mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def completed_run(
        *,
        run_id="autonomy-1",
        success=True,
        status=None,
        retries=0,
        failures=0,
        rollback=False,
        subsystem="app.demo",
    ):
        final_status = status or (
            "FULL_AUTONOMY_COMPLETED"
            if success
            else "FULL_AUTONOMY_FAILED"
        )
        return {
            "run_id": run_id,
            "goal_id": f"goal-{run_id}",
            "portfolio_id": f"portfolio-{run_id}",
            "director_run_id": f"director-{run_id}",
            "objective": "Utwórz moduł demonstracyjny",
            "status": final_status,
            "success": success,
            "started_at": "2026-07-16T10:00:00+00:00",
            "completed_at": "2026-07-16T10:10:00+00:00",
            "plan": {
                "target_files": [
                    "app/demo/models.py",
                    "tests/test_demo.py",
                ],
                "subsystems": [subsystem, "tests"],
                "campaigns": [{}, {}],
                "estimated_roi": 0.8,
                "estimated_risk": 0.3,
                "estimated_minutes": 20,
                "confidence": 0.9,
            },
            "execution": {
                "stages_total": 4,
                "changed_files": [
                    "app/demo/models.py",
                    "tests/test_demo.py",
                ],
                "progress_percent": 100.0 if success else 50.0,
            },
            "director_result": {
                "director_run": {
                    "retries": retries,
                    "failures": failures,
                }
            },
            "final_validation": {
                "success": success,
            },
            "rollback": {
                "success": rollback,
            } if rollback else {},
            "errors": [] if success else ["ValidationError: demo"],
        }

    @staticmethod
    def episode(
        *,
        episode_id="episode-1",
        success=True,
        rolled_back=False,
        retries=0,
        risk=3.0,
        roi=8.0,
        subsystem="app.demo",
        signature="sig-1",
    ):
        return {
            "episode_id": episode_id,
            "episode_type": "full_autonomy",
            "source": "test",
            "source_id": episode_id,
            "objective": "Demo",
            "signature": signature,
            "status": (
                "FULL_AUTONOMY_COMPLETED"
                if success
                else "FULL_AUTONOMY_FAILED"
            ),
            "success": success,
            "rolled_back": rolled_back,
            "retry_count": retries,
            "failure_count": 0 if success else 1,
            "started_at": "2026-07-16T10:00:00+00:00",
            "completed_at": "2026-07-16T10:10:00+00:00",
            "duration_seconds": 600.0,
            "actual_minutes": 10.0,
            "estimated_roi": roi,
            "estimated_risk": risk,
            "estimated_minutes": 20.0,
            "confidence": 0.8,
            "subsystems": [subsystem],
            "targets": ["app/demo.py"],
            "target_count": 1,
            "campaign_count": 1,
            "stage_count": 2,
            "changed_files_count": 1,
            "errors": [] if success else ["Repeated error"],
            "metadata": {},
        }

    def test_store_persists_episode_and_profile(self):
        store = AutonomousLearningStore(self.root)
        stored, created = store.save_episode(
            self.episode()
        )
        profile = store.save_profile({
            "active": True,
            "observations": 5,
            "confidence": 0.7,
        })

        self.assertTrue(created)
        self.assertEqual(
            stored["episode_id"],
            "episode-1",
        )
        self.assertTrue(profile["active"])
        reopened = AutonomousLearningStore(self.root)
        self.assertEqual(
            len(reopened.list_episodes(limit=10)),
            1,
        )
        self.assertTrue(
            reopened.get_profile()["active"]
        )

    def test_store_updates_duplicate_episode(self):
        store = AutonomousLearningStore(self.root)
        store.save_episode(self.episode())
        changed = self.episode(success=False)
        _, created = store.save_episode(changed)

        self.assertFalse(created)
        self.assertFalse(
            store.get_episode("episode-1")["success"]
        )
        self.assertEqual(
            len(store.list_episodes(limit=10)),
            1,
        )

    def test_store_bounds_episode_history(self):
        store = AutonomousLearningStore(
            self.root,
            max_episodes=100,
        )
        for index in range(110):
            store.save_episode(
                self.episode(
                    episode_id=f"episode-{index}"
                )
            )

        self.assertEqual(
            len(store.list_episodes(limit=200)),
            100,
        )
        self.assertIsNone(
            store.get_episode("episode-0")
        )

    def test_store_recovers_from_corrupt_json(self):
        store = AutonomousLearningStore(self.root)
        store.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )
        store.path.write_text(
            "{broken",
            encoding="utf-8",
        )

        summary = store.summary()

        self.assertEqual(summary["episodes"], 0)
        self.assertFalse(summary["profile_active"])

    def test_collector_normalizes_completed_full_run(self):
        collector = AutonomyHistoryCollector(
            self.root,
            full_store=FakeListStore([
                self.completed_run()
            ]),
            portfolio_store=FakeListStore(),
            campaign_store=FakeListStore(),
            director_store=FakeListStore(),
        )

        result = collector.collect()

        self.assertEqual(
            result["episodes_count"],
            1,
        )
        episode = result["episodes"][0]
        self.assertTrue(episode["success"])
        self.assertEqual(
            episode["estimated_roi"],
            8.0,
        )
        self.assertEqual(
            episode["estimated_risk"],
            3.0,
        )
        self.assertEqual(
            episode["duration_seconds"],
            600.0,
        )

    def test_collector_skips_nonterminal_full_run(self):
        collector = AutonomyHistoryCollector(
            self.root,
            full_store=FakeListStore([
                self.completed_run(
                    status="FULL_AUTONOMY_PLAN_READY",
                    success=False,
                )
            ]),
            portfolio_store=FakeListStore(),
            campaign_store=FakeListStore(),
            director_store=FakeListStore(),
        )

        self.assertEqual(
            collector.collect()["episodes_count"],
            0,
        )

    def test_collector_records_rollback_and_retry(self):
        run = self.completed_run(
            success=False,
            status=(
                "FULL_AUTONOMY_FINAL_VALIDATION_"
                "FAILED_AND_ROLLED_BACK"
            ),
            retries=2,
            failures=1,
            rollback=True,
        )
        collector = AutonomyHistoryCollector(self.root)
        episode = collector.from_full_run(run)

        self.assertIsNotNone(episode)
        self.assertTrue(episode["rolled_back"])
        self.assertEqual(episode["retry_count"], 2)
        self.assertEqual(episode["failure_count"], 1)

    def test_collector_normalizes_portfolio_campaign(self):
        collector = AutonomyHistoryCollector(self.root)
        portfolio = {
            "portfolio_id": "portfolio-1",
            "campaigns": [],
        }
        campaign = {
            "campaign_id": "campaign-1",
            "objective": "Zmień moduł",
            "status": "COMPLETED",
            "targets": ["app/x.py"],
            "stages": [{}, {}],
            "metadata": {
                "estimated_roi": 7,
                "estimated_risk": 2,
                "subsystems": ["app.x"],
            },
            "result": {
                "status": "COMPLETED",
                "attempts": 1,
                "changed_files": ["app/x.py"],
            },
        }

        episode = collector.from_portfolio_campaign(
            portfolio,
            campaign,
        )

        self.assertTrue(episode["success"])
        self.assertEqual(
            episode["episode_type"],
            "portfolio_campaign",
        )
        self.assertEqual(episode["stage_count"], 2)

    def test_collector_deduplicates_sources(self):
        run = self.completed_run()
        collector = AutonomyHistoryCollector(
            self.root,
            full_store=FakeListStore([run, run]),
            portfolio_store=FakeListStore(),
            campaign_store=FakeListStore(),
            director_store=FakeListStore(),
        )

        self.assertEqual(
            collector.collect()["episodes_count"],
            1,
        )

    def test_analyzer_computes_rates(self):
        analyzer = AutonomyOutcomeAnalyzer()
        result = analyzer.analyze([
            self.episode(
                episode_id="a",
                success=True,
            ),
            self.episode(
                episode_id="b",
                success=False,
                rolled_back=True,
                retries=1,
            ),
        ])

        self.assertEqual(result["observations"], 2)
        self.assertEqual(result["success_rate"], 0.5)
        self.assertEqual(result["rollback_rate"], 0.5)
        self.assertEqual(result["retry_rate"], 0.5)

    def test_analyzer_builds_subsystem_patterns(self):
        analyzer = AutonomyOutcomeAnalyzer()
        result = analyzer.analyze([
            self.episode(
                episode_id="a",
                success=False,
                subsystem="app.risky",
            ),
            self.episode(
                episode_id="b",
                success=False,
                subsystem="app.risky",
            ),
        ])

        risky = result["subsystems"]["app.risky"]
        self.assertEqual(risky["observations"], 2)
        self.assertEqual(risky["success_rate"], 0.0)
        self.assertTrue(
            any(
                item["kind"] == "subsystem_risk"
                for item in result["lessons"]
            )
        )

    def test_analyzer_detects_risk_underestimation(self):
        analyzer = AutonomyOutcomeAnalyzer()
        result = analyzer.analyze([
            self.episode(
                episode_id="a",
                success=False,
                risk=1.0,
            )
        ])

        self.assertGreater(
            result["calibration"]["risk_underestimation"],
            5.0,
        )

    def test_analyzer_handles_empty_history(self):
        result = AutonomyOutcomeAnalyzer().analyze([])

        self.assertEqual(result["observations"], 0)
        self.assertEqual(result["success_rate"], 0.0)
        self.assertTrue(result["recommendations"])

    def test_policy_learner_requires_minimum_data(self):
        learner = AutonomyPolicyLearner(
            minimum_observations=5
        )
        result = learner.propose(
            {
                "observations": 2,
                "success_rate": 1.0,
                "rollback_rate": 0.0,
                "retry_rate": 0.0,
                "calibration": {},
                "recommendations": [],
            },
            apply_requested=True,
        )

        self.assertFalse(result["applied"])
        self.assertFalse(result["profile"]["active"])
        self.assertEqual(
            result["status"],
            "AUTONOMOUS_LEARNING_INSUFFICIENT_DATA",
        )

    def test_policy_learner_applies_with_enough_data(self):
        result = AutonomyPolicyLearner().propose(
            {
                "observations": 10,
                "success_rate": 0.9,
                "rollback_rate": 0.0,
                "retry_rate": 0.1,
                "calibration": {},
                "recommendations": [],
            },
            apply_requested=True,
        )

        self.assertTrue(result["applied"])
        self.assertTrue(result["profile"]["active"])
        self.assertAlmostEqual(
            sum(
                result["profile"][
                    "optimizer_weights"
                ].values()
            ),
            1.0,
            places=5,
        )

    def test_policy_learner_increases_risk_weight_after_failures(self):
        result = AutonomyPolicyLearner().propose(
            {
                "observations": 10,
                "success_rate": 0.4,
                "rollback_rate": 0.3,
                "retry_rate": 0.4,
                "calibration": {
                    "risk_underestimation": 5.0,
                    "roi_overestimation": 5.0,
                },
                "recommendations": [],
            }
        )
        weights = result["profile"]["optimizer_weights"]

        self.assertGreater(weights["risk"], 0.22)
        self.assertGreater(weights["history"], 0.18)
        self.assertLessEqual(
            result["profile"][
                "optimizer_constraints"
            ]["max_risk"],
            5.0,
        )

    def test_policy_learner_never_enables_automatic_approval(self):
        result = AutonomyPolicyLearner().propose(
            {
                "observations": 30,
                "success_rate": 1.0,
                "rollback_rate": 0.0,
                "retry_rate": 0.0,
                "calibration": {},
                "recommendations": [],
            },
            apply_requested=True,
        )

        safety = result["profile"]["safety"]
        self.assertFalse(safety["auto_approve"])
        self.assertTrue(safety["auto_rollback"])
        self.assertTrue(safety["final_validation"])

    def test_engine_learns_and_persists_training_run(self):
        collector = MagicMock()
        collector.collect.return_value = {
            "episodes": [
                self.episode(
                    episode_id=f"e-{index}"
                )
                for index in range(6)
            ],
            "episodes_count": 6,
            "source_counts": {
                "full_autonomy": 6,
            },
        }
        engine = AutonomousLearningEngine(
            self.root,
            collector=collector,
        )

        result = engine.learn(apply=True)

        self.assertTrue(result["applied"])
        self.assertEqual(
            len(engine.store.list_training_runs(limit=10)),
            1,
        )
        self.assertTrue(
            engine.store.get_profile()["active"]
        )

    def test_engine_observe_run_is_idempotent(self):
        engine = AutonomousLearningEngine(self.root)
        run = self.completed_run()

        first = engine.observe_run(run)
        second = engine.observe_run(run)

        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(
            engine.store.summary()["episodes"],
            1,
        )

    def test_engine_skips_nonterminal_observation(self):
        engine = AutonomousLearningEngine(self.root)
        run = self.completed_run(
            status="FULL_AUTONOMY_RUNNING",
            success=False,
        )

        result = engine.observe_run(run)

        self.assertEqual(
            result["status"],
            "AUTONOMOUS_LEARNING_OBSERVATION_SKIPPED",
        )
        self.assertEqual(
            engine.store.summary()["episodes"],
            0,
        )

    def test_engine_status_profile_history_and_explain(self):
        engine = AutonomousLearningEngine(self.root)
        engine.store.save_episode(
            self.episode()
        )
        engine.store.save_training_run({
            "training_run_id": "learning-1",
            "status": "OK",
        })

        self.assertEqual(
            engine.status()["status"],
            "AUTONOMOUS_LEARNING_STATUS",
        )
        self.assertEqual(
            engine.profile()["status"],
            "AUTONOMOUS_LEARNING_PROFILE",
        )
        self.assertEqual(
            len(engine.history()["episodes"]),
            1,
        )
        self.assertEqual(
            engine.explain(
                subsystem="app.demo"
            )["matches"],
            1,
        )

    def test_learning_router_detects_polish_command(self):
        router = SoftwareEngineerLearningRouter()
        controller = SimpleNamespace(
            project_root=self.root,
            _normalize=lambda value: str(value).casefold(),
        )

        self.assertTrue(
            router._is_learning(
                controller,
                command="Naucz JARVIS-a na historii autonomii",
                context={},
            )
        )

    def test_learning_router_routes_apply(self):
        engine = MagicMock()
        engine.learn.return_value = {
            "success": True,
            "status": "AUTONOMOUS_LEARNING_PROFILE_APPLIED",
            "operation": "autonomous_learning",
        }
        controller = SimpleNamespace(
            project_root=self.root,
            autonomous_learning_engine=engine,
            _normalize=lambda value: str(value).casefold(),
        )

        result = SoftwareEngineerLearningRouter().try_handle(
            controller,
            command="Zastosuj naukę autonomii",
            objective="",
            context={},
        )

        self.assertEqual(
            result["status"],
            "AUTONOMOUS_LEARNING_PROFILE_APPLIED",
        )
        engine.learn.assert_called_once_with(
            limit=500,
            apply=True,
        )

    def test_learning_router_routes_status_from_context(self):
        engine = MagicMock()
        engine.status.return_value = {
            "success": True,
            "status": "AUTONOMOUS_LEARNING_STATUS",
            "operation": "autonomous_learning",
        }
        controller = SimpleNamespace(
            project_root=self.root,
            autonomous_learning_engine=engine,
            _normalize=lambda value: str(value).casefold(),
        )

        result = SoftwareEngineerLearningRouter().try_handle(
            controller,
            command="x",
            objective="",
            context={
                "operation": "autonomous_learning",
                "learning_action": "status",
            },
        )

        self.assertEqual(
            result["status"],
            "AUTONOMOUS_LEARNING_STATUS",
        )
        engine.status.assert_called_once()

    def test_learning_formatter_reports_metrics(self):
        text = format_autonomous_learning_response({
            "status": "AUTONOMOUS_LEARNING_PROFILE_APPLIED",
            "training_run_id": "learning-1",
            "analysis": {
                "observations": 10,
                "success_rate": 0.9,
                "rollback_rate": 0.1,
                "retry_rate": 0.2,
            },
            "profile": {
                "active": True,
                "confidence": 0.8,
                "optimizer_constraints": {
                    "min_score": 40,
                    "max_risk": 7,
                    "max_campaigns": 8,
                },
                "recommendations": ["Kontynuuj naukę."],
            },
            "report_path": "data/autodev/autonomous_learning.json",
        })

        self.assertIn("Obserwacje: 10", text)
        self.assertIn("Skuteczność: 90.0%", text)
        self.assertIn("Profil aktywny: TAK", text)
        self.assertIn("Kontynuuj naukę", text)

    def test_brain_formatter_routes_learning_operation(self):
        formatter = BrainResponseFormatter()

        text = formatter._format_software_engineer_response({
            "success": True,
            "status": "AUTONOMOUS_LEARNING_STATUS",
            "operation": "autonomous_learning",
            "profile": {
                "active": False,
                "observations": 0,
                "confidence": 0.0,
            },
        })

        self.assertIn("Uczenie autonomii", text)

    def test_optimizer_uses_active_learning_profile(self):
        learning_store = AutonomousLearningStore(self.root)
        learning_store.save_profile({
            "active": True,
            "observations": 10,
            "confidence": 0.8,
            "optimizer_weights": {
                "roi": 0.1,
                "risk": 0.5,
                "time": 0.1,
                "history": 0.1,
                "priority": 0.1,
                "confidence": 0.1,
            },
            "optimizer_constraints": {
                "min_score": 10,
                "max_risk": 4,
                "max_campaigns": 2,
                "require_positive_roi": False,
            },
        })
        optimizer = PortfolioOptimizer(
            self.root,
            store=FakeListStore(),
            learning_store=learning_store,
        )
        portfolio = MultiCampaignPortfolio(
            portfolio_id="p1",
            objective="Demo",
            campaigns=[
                ManagedCampaign(
                    campaign_id="c1",
                    objective="Demo",
                    stages=[{}],
                    targets=["app/demo.py"],
                    metadata={
                        "estimated_roi": 8,
                        "estimated_risk": 3,
                        "estimated_minutes": 10,
                        "confidence": 0.8,
                    },
                )
            ],
            execution_order=["c1"],
            fingerprint="fp",
        )

        result = optimizer.optimize(portfolio)

        self.assertTrue(
            result["learning_profile"]["active"]
        )
        self.assertEqual(
            result["constraints"]["max_risk"],
            4.0,
        )
        self.assertAlmostEqual(
            result["weights"]["risk"],
            0.5,
            places=5,
        )

    def test_optimizer_user_constraints_override_learning_profile(self):
        learning_store = AutonomousLearningStore(self.root)
        learning_store.save_profile({
            "active": True,
            "optimizer_constraints": {
                "min_score": 70,
                "max_risk": 4,
                "max_campaigns": 2,
            },
        })
        optimizer = PortfolioOptimizer(
            self.root,
            store=FakeListStore(),
            learning_store=learning_store,
        )
        portfolio = MultiCampaignPortfolio(
            portfolio_id="p1",
            objective="Demo",
            campaigns=[
                ManagedCampaign(
                    campaign_id="c1",
                    objective="Demo",
                    stages=[{}],
                    targets=["app/demo.py"],
                )
            ],
            execution_order=["c1"],
            fingerprint="fp",
        )

        result = optimizer.optimize(
            portfolio,
            constraints={
                "max_risk": 9,
            },
        )

        self.assertEqual(
            result["constraints"]["max_risk"],
            9.0,
        )

    def test_full_workflow_applies_active_learning_defaults(self):
        workflow = FullAutonomyWorkflow.__new__(
            FullAutonomyWorkflow
        )
        profile = AutonomousLearningStore.default_profile()
        profile.update({
            "active": True,
            "confidence": 0.8,
            "observations": 10,
            "source_training_run_id": "learning-1",
            "optimizer_constraints": {
                "min_score": 55,
                "max_risk": 6,
                "max_campaigns": 5,
            },
            "optimizer_weights": {
                "roi": 0.2,
                "risk": 0.3,
                "time": 0.1,
                "history": 0.2,
                "priority": 0.1,
                "confidence": 0.1,
            },
            "director_policy": {
                "max_retries_per_campaign": 0,
                "max_failures": 1,
                "rollback_on_stop": True,
            },
        })
        workflow.learning_engine = SimpleNamespace(
            store=SimpleNamespace(
                get_profile=lambda: profile
            )
        )

        values = workflow._apply_learning_policy({})

        self.assertEqual(
            values["max_retries_per_campaign"],
            0,
        )
        self.assertEqual(values["max_failures"], 1)
        self.assertEqual(
            values["optimization_constraints"]["max_risk"],
            6,
        )

    def test_full_workflow_terminal_save_records_learning(self):
        workflow = FullAutonomyWorkflow.__new__(
            FullAutonomyWorkflow
        )
        saved = {}
        workflow.store = SimpleNamespace(
            save=lambda value: saved.update(value) or dict(value)
        )
        observer = MagicMock(
            return_value={
                "success": True,
                "status": (
                    "AUTONOMOUS_LEARNING_EPISODE_RECORDED"
                ),
            }
        )
        workflow.learning_engine = SimpleNamespace(
            observe_run=observer
        )
        run = self.completed_run()

        result = workflow._save_terminal(run)

        observer.assert_called_once()
        self.assertIn(
            "learning_observation",
            result,
        )
        self.assertEqual(
            result["learning_observation"]["status"],
            "AUTONOMOUS_LEARNING_EPISODE_RECORDED",
        )


if __name__ == "__main__":
    unittest.main()
