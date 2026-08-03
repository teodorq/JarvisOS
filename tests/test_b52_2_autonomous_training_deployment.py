"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import json
import unittest
from unittest.mock import MagicMock

from app.ai.software_engineer.autonomous_learning_engine import (
    AutonomousLearningEngine,
)
from app.ai.software_engineer.autonomous_learning_store import (
    AutonomousLearningStore,
)
from app.ai.software_engineer.autonomous_profile_deployer import (
    AutonomousProfileDeployer,
)
from app.ai.software_engineer.autonomous_training_scheduler import (
    AutonomousTrainingScheduler,
)
from app.ai.software_engineer.autonomous_software_engineer import (
    AutonomousSoftwareEngineerController,
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


class FakeCollector:

    def __init__(self, episodes):
        self.episodes = list(episodes)

    def from_full_run(self, run):
        return dict(run.get("episode", {})) or None

    def collect(self, *, limit=500):
        return {
            "episodes": [dict(item) for item in self.episodes[:limit]],
            "episodes_count": len(self.episodes[:limit]),
            "source_counts": {"full_autonomy": len(self.episodes[:limit])},
        }


class FakeListStore:

    def list_recent(self, *, limit=20):
        return []


class B522AutonomousTrainingDeploymentTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp = TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "app").mkdir()
        (self.root / "tests").mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def episode(index=1, *, success=True):
        return {
            "episode_id": f"episode-{index}",
            "episode_type": "full_autonomy",
            "source": "test",
            "source_id": f"autonomy-{index}",
            "objective": "Demo",
            "signature": "demo",
            "status": (
                "FULL_AUTONOMY_COMPLETED"
                if success
                else "FULL_AUTONOMY_FAILED"
            ),
            "success": success,
            "rolled_back": not success,
            "retry_count": 0,
            "failure_count": 0 if success else 1,
            "started_at": "2026-07-16T10:00:00+00:00",
            "completed_at": "2026-07-16T10:10:00+00:00",
            "duration_seconds": 600.0,
            "actual_minutes": 10.0,
            "estimated_roi": 8.0,
            "estimated_risk": 3.0,
            "estimated_minutes": 20.0,
            "confidence": 0.8,
            "subsystems": ["app.demo"],
            "targets": ["app/demo.py"],
            "target_count": 1,
            "campaign_count": 1,
            "stage_count": 2,
            "changed_files_count": 1,
            "errors": [] if success else ["Demo failure"],
            "metadata": {},
        }

    @staticmethod
    def safe_profile(*, confidence=0.5, observations=10):
        return {
            "active": False,
            "observations": observations,
            "confidence": confidence,
            "optimizer_weights": {
                "roi": 0.25,
                "risk": 0.25,
                "time": 0.10,
                "history": 0.20,
                "priority": 0.10,
                "confidence": 0.10,
            },
            "optimizer_constraints": {
                "min_score": 35.0,
                "max_risk": 7.0,
                "max_campaigns": 10,
                "require_positive_roi": False,
            },
            "director_policy": {
                "max_retries_per_campaign": 1,
                "max_failures": 2,
                "rollback_on_stop": True,
            },
            "safety": {
                "auto_approve": False,
                "auto_rollback": True,
                "final_validation": True,
                "code_writes": False,
            },
        }

    def test_scheduler_waits_for_minimum_observations(self):
        result = AutonomousTrainingScheduler().evaluate(
            summary={"episodes": 4},
            state={"auto_training_enabled": True},
        )

        self.assertFalse(result["ready"])
        self.assertEqual(
            result["status"],
            "AUTONOMOUS_TRAINING_WAITING_FOR_DATA",
        )

    def test_scheduler_is_ready_after_threshold(self):
        result = AutonomousTrainingScheduler().evaluate(
            summary={"episodes": 5},
            state={
                "auto_training_enabled": True,
                "last_trained_episode_count": 4,
            },
        )

        self.assertTrue(result["ready"])
        self.assertEqual(result["new_episodes"], 1)

    def test_scheduler_does_not_repeat_without_new_episode(self):
        result = AutonomousTrainingScheduler().evaluate(
            summary={"episodes": 5},
            state={
                "auto_training_enabled": True,
                "last_trained_episode_count": 5,
            },
        )

        self.assertFalse(result["ready"])
        self.assertEqual(
            result["status"],
            "AUTONOMOUS_TRAINING_WAITING_FOR_NEW_DATA",
        )

    def test_store_migrates_version_one_payload(self):
        store = AutonomousLearningStore(self.root)
        store.path.parent.mkdir(parents=True, exist_ok=True)
        store.path.write_text(
            json.dumps({
                "version": 1,
                "profile": {"active": False},
                "episodes": {},
                "episode_order": [],
                "training_runs": {},
                "training_order": [],
            }),
            encoding="utf-8",
        )

        summary = store.summary()

        self.assertEqual(summary["profile_versions"], 0)
        self.assertTrue(summary["auto_training_enabled"])

    def test_store_versions_and_activates_profile(self):
        store = AutonomousLearningStore(self.root)
        version = store.save_profile_version(
            self.safe_profile(),
            training_run_id="learning-1",
        )
        activated = store.activate_profile_version(
            version["version_id"],
            decision={"eligible": True},
        )

        self.assertEqual(activated["deployment_status"], "ACTIVE")
        self.assertTrue(store.get_profile()["active"])
        self.assertEqual(
            store.get_profile()["profile_version_id"],
            version["version_id"],
        )

    def test_activation_archives_previous_profile(self):
        store = AutonomousLearningStore(self.root)
        first = store.save_profile_version(
            self.safe_profile(confidence=0.4),
            training_run_id="learning-1",
        )
        second = store.save_profile_version(
            self.safe_profile(confidence=0.5),
            training_run_id="learning-2",
        )
        store.activate_profile_version(first["version_id"])
        store.activate_profile_version(second["version_id"])

        self.assertEqual(
            store.get_profile_version(first["version_id"])[
                "deployment_status"
            ],
            "ARCHIVED",
        )

    def test_store_rolls_back_to_previous_profile(self):
        store = AutonomousLearningStore(self.root)
        first = store.save_profile_version(
            self.safe_profile(confidence=0.4),
            training_run_id="learning-1",
        )
        second = store.save_profile_version(
            self.safe_profile(confidence=0.5),
            training_run_id="learning-2",
        )
        store.activate_profile_version(first["version_id"])
        store.activate_profile_version(second["version_id"])

        result = store.rollback_profile()

        self.assertTrue(result["success"])
        self.assertEqual(
            store.get_profile()["profile_version_id"],
            first["version_id"],
        )

    def test_deployer_rejects_auto_approval(self):
        profile = self.safe_profile()
        profile["safety"]["auto_approve"] = True

        result = AutonomousProfileDeployer().evaluate(profile)

        self.assertFalse(result["eligible"])
        self.assertTrue(result["hard_rejection"])
        self.assertEqual(result["status"], "AUTONOMOUS_PROFILE_REJECTED")

    def test_deployer_stages_low_confidence_profile(self):
        result = AutonomousProfileDeployer(
            minimum_confidence=0.4
        ).evaluate(
            self.safe_profile(confidence=0.2)
        )

        self.assertFalse(result["eligible"])
        self.assertFalse(result["hard_rejection"])
        self.assertEqual(result["status"], "AUTONOMOUS_PROFILE_STAGED")

    def test_deployer_activates_safe_profile(self):
        store = AutonomousLearningStore(self.root)
        version = store.save_profile_version(
            self.safe_profile(),
            training_run_id="learning-1",
        )

        result = AutonomousProfileDeployer().deploy(
            store,
            version["version_id"],
        )

        self.assertTrue(result["applied"])
        self.assertTrue(store.get_profile()["active"])

    def test_engine_auto_trains_on_fifth_episode(self):
        episodes = [self.episode(index) for index in range(1, 6)]
        collector = FakeCollector(episodes)
        engine = AutonomousLearningEngine(
            self.root,
            collector=collector,
        )
        for item in episodes[:4]:
            engine.store.save_episode(item)

        result = engine.observe_run({"episode": episodes[4]})

        self.assertTrue(result["created"])
        self.assertEqual(
            result["auto_training"]["status"],
            "AUTONOMOUS_TRAINING_PROFILE_DEPLOYED",
        )
        self.assertTrue(engine.store.get_profile()["active"])
        self.assertEqual(engine.store.summary()["training_runs"], 1)

    def test_duplicate_episode_does_not_repeat_training(self):
        episodes = [self.episode(index) for index in range(1, 6)]
        engine = AutonomousLearningEngine(
            self.root,
            collector=FakeCollector(episodes),
        )
        for item in episodes:
            engine.store.save_episode(item)
        engine.store.update_training_state({
            "last_trained_episode_count": 5,
        })

        result = engine.observe_run({"episode": episodes[-1]})

        self.assertFalse(result["created"])
        self.assertEqual(
            result["auto_training"]["status"],
            "AUTONOMOUS_TRAINING_DUPLICATE_EPISODE_SKIPPED",
        )
        self.assertEqual(engine.store.summary()["training_runs"], 0)

    def test_engine_can_disable_auto_training(self):
        engine = AutonomousLearningEngine(self.root)

        result = engine.configure_auto_training(enabled=False)

        self.assertFalse(
            result["training_state"]["auto_training_enabled"]
        )
        self.assertEqual(
            result["auto_training"]["status"],
            "AUTONOMOUS_TRAINING_DISABLED",
        )

    def test_engine_lists_profile_versions(self):
        store = AutonomousLearningStore(self.root)
        store.save_profile_version(
            self.safe_profile(),
            training_run_id="learning-1",
        )
        engine = AutonomousLearningEngine(self.root, store=store)

        result = engine.versions()

        self.assertEqual(
            result["status"],
            "AUTONOMOUS_LEARNING_PROFILE_VERSIONS",
        )
        self.assertEqual(len(result["profile_versions"]), 1)

    def test_router_routes_profile_versions(self):
        engine = MagicMock()
        engine.versions.return_value = {
            "success": True,
            "status": "AUTONOMOUS_LEARNING_PROFILE_VERSIONS",
            "operation": "autonomous_learning",
        }
        controller = SimpleNamespace(
            project_root=self.root,
            autonomous_learning_engine=engine,
            _normalize=lambda value: str(value).casefold(),
        )

        result = SoftwareEngineerLearningRouter().try_handle(
            controller,
            command="Pokaż wersje profilu uczenia",
            objective="",
            context={},
        )

        self.assertEqual(
            result["status"],
            "AUTONOMOUS_LEARNING_PROFILE_VERSIONS",
        )
        engine.versions.assert_called_once_with(limit=20)

    def test_router_routes_profile_rollback(self):
        engine = MagicMock()
        engine.rollback_profile.return_value = {
            "success": True,
            "status": "AUTONOMOUS_PROFILE_ROLLED_BACK",
            "operation": "autonomous_learning",
        }
        controller = SimpleNamespace(
            project_root=self.root,
            autonomous_learning_engine=engine,
            _normalize=lambda value: str(value).casefold(),
        )

        result = SoftwareEngineerLearningRouter().try_handle(
            controller,
            command="Cofnij profil uczenia",
            objective="",
            context={},
        )

        self.assertEqual(result["status"], "AUTONOMOUS_PROFILE_ROLLED_BACK")
        engine.rollback_profile.assert_called_once_with()

    def test_formatter_reports_auto_training_and_versions(self):
        text = format_autonomous_learning_response({
            "status": "AUTONOMOUS_LEARNING_STATUS",
            "profile": {
                "active": True,
                "confidence": 0.6,
                "profile_version_id": "profile-abc12345",
            },
            "training_state": {
                "auto_training_enabled": True,
                "minimum_observations": 5,
                "minimum_new_episodes": 1,
            },
            "auto_training": {
                "status": "AUTONOMOUS_TRAINING_WAITING_FOR_NEW_DATA",
            },
            "profile_versions": [{
                "version_id": "profile-abc12345",
                "deployment_status": "ACTIVE",
                "profile": {"confidence": 0.6},
            }],
            "store": {
                "episodes": 5,
                "training_runs": 1,
                "active_profile_version_id": "profile-abc12345",
            },
        })

        self.assertIn("Automatyczny trening: WŁĄCZONY", text)
        self.assertIn("Próg treningu: 5 epizodów", text)
        self.assertIn("Aktywna wersja profilu", text)
        self.assertIn("Wersje profilu: 1", text)

    def test_workflow_ignores_unapproved_versioned_profile(self):
        workflow = FullAutonomyWorkflow.__new__(FullAutonomyWorkflow)
        profile = self.safe_profile()
        profile.update({
            "active": True,
            "profile_version_id": "profile-abc12345",
            "deployment": {"approved": False},
            "director_policy": {
                "max_retries_per_campaign": 0,
                "max_failures": 1,
                "rollback_on_stop": True,
            },
        })
        workflow.learning_engine = SimpleNamespace(
            store=SimpleNamespace(get_profile=lambda: profile)
        )

        values = workflow._apply_learning_policy({})

        self.assertNotIn("max_failures", values)
        self.assertNotIn("learning_profile", values)

    def test_optimizer_ignores_unapproved_versioned_profile(self):
        learning_store = AutonomousLearningStore(self.root)
        learning_store.save_profile({
            **self.safe_profile(),
            "active": True,
            "profile_version_id": "profile-unapproved",
            "deployment": {"approved": False},
            "optimizer_constraints": {
                "min_score": 99,
                "max_risk": 1,
                "max_campaigns": 1,
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

        result = optimizer.optimize(portfolio)

        self.assertFalse(result["learning_profile"]["active"])
        self.assertEqual(result["constraints"]["min_score"], 0.0)


    def test_engine_insufficient_data_does_not_deploy(self):
        episodes = [self.episode(1)]
        deployer = MagicMock()
        engine = AutonomousLearningEngine(
            self.root,
            collector=FakeCollector(episodes),
            deployer=deployer,
        )

        result = engine.learn(apply=True)

        self.assertEqual(
            result["status"],
            "AUTONOMOUS_LEARNING_INSUFFICIENT_DATA",
        )
        self.assertFalse(result["applied"])
        deployer.deploy.assert_not_called()

    def test_controller_accepts_profile_version_commands(self):
        for command in (
            "Pokaż wersje profilu uczenia",
            "Cofnij profil uczenia",
            "Włącz automatyczny trening",
        ):
            with self.subTest(command=command):
                self.assertTrue(
                    AutonomousSoftwareEngineerController.can_handle(command)
                )

    def test_workflow_applies_safely_deployed_version(self):
        workflow = FullAutonomyWorkflow.__new__(FullAutonomyWorkflow)
        profile = self.safe_profile(confidence=0.5, observations=10)
        profile.update({
            "active": True,
            "profile_version_id": "profile-approved",
            "deployment": {
                "approved": True,
                "decision": {"minimum_confidence": 0.1},
            },
            "director_policy": {
                "max_retries_per_campaign": 0,
                "max_failures": 1,
                "rollback_on_stop": True,
            },
        })
        workflow.learning_engine = SimpleNamespace(
            store=SimpleNamespace(get_profile=lambda: profile)
        )

        values = workflow._apply_learning_policy({})

        self.assertEqual(values["max_failures"], 1)
        self.assertEqual(values["max_retries_per_campaign"], 0)
        self.assertTrue(values["learning_profile"]["active"])

    def test_training_state_is_persisted(self):
        store = AutonomousLearningStore(self.root)
        store.update_training_state({
            "minimum_observations": 8,
            "minimum_confidence": 0.3,
        })

        reopened = AutonomousLearningStore(self.root)
        state = reopened.get_training_state()

        self.assertEqual(state["minimum_observations"], 8)
        self.assertEqual(state["minimum_confidence"], 0.3)


if __name__ == "__main__":
    unittest.main()
