from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import MagicMock, patch
import unittest

from app.ai.brain_response_formatter import BrainResponseFormatter
from app.ai.software_engineer.project_intelligence_models import (
    ProjectOpportunity,
)
from app.ai.software_engineer.project_intelligence_ranker import (
    ProjectOpportunityRanker,
)
from app.ai.software_engineer.project_intelligence_service import (
    ProjectIntelligenceService,
)
from app.ai.software_engineer.project_intelligence_store import (
    ProjectIntelligenceStore,
)
from app.ai.software_engineer.self_directed_development_service import (
    SelfDirectedDevelopmentService,
)
from app.ai.software_engineer.self_directed_development_store import (
    SelfDirectedDevelopmentStore,
)
from app.ai.software_engineer.software_engineer_strategic_development_formatter import (
    format_strategic_development_response,
)
from app.ai.software_engineer.software_engineer_strategic_development_router import (
    SoftwareEngineerStrategicDevelopmentRouter,
)
from app.ai.software_engineer.strategic_development_models import (
    StrategicDevelopmentPolicy,
)
from app.ai.software_engineer.strategic_development_planner import (
    StrategicDevelopmentPlanner,
)
from app.ai.software_engineer.strategic_development_service import (
    StrategicDevelopmentService,
    bootstrap_strategic_development,
)
from app.ai.software_engineer.strategic_development_store import (
    StrategicDevelopmentStore,
)
from app.gui.command_safety import is_read_only_learning_command


def opportunity(
    *,
    opportunity_id: str,
    target: str,
    issue_type: str = "LARGE_MODULE",
    status: str = "PENDING",
    value: float = 60.0,
    risk: float = 10.0,
    confidence: float = 0.9,
) -> dict:
    return ProjectOpportunity(
        opportunity_id=opportunity_id,
        title=f"Popraw {target}",
        objective=f"Bezpiecznie popraw {target}.",
        target=target,
        fingerprint=f"{opportunity_id}-{target}",
        issue_type=issue_type,
        value_score=value,
        risk_score=risk,
        effort_score=5.0,
        confidence=confidence,
        final_score=70.0,
        status=status,
    ).to_dict()


class B57ModelsStoreTests(unittest.TestCase):

    def test_policy_never_auto_approves_and_bounds_limits(self) -> None:
        policy = StrategicDevelopmentPolicy.from_dict({
            "auto_approve": True,
            "refresh_interval_seconds": 1,
            "max_goals": 9999,
            "max_active_goals": 9,
        })
        self.assertFalse(policy.auto_approve)
        self.assertEqual(policy.refresh_interval_seconds, 60.0)
        self.assertEqual(policy.max_goals, 500)
        self.assertEqual(policy.max_active_goals, 1)

    def test_store_persists_runtime_policy_and_goals(self) -> None:
        with TemporaryDirectory() as directory:
            store = StrategicDevelopmentStore(directory)
            store.update_runtime({
                "enabled": True,
                "active_goal_id": "strategic-one",
            })
            store.update_policy({"auto_approve": True})
            planner = StrategicDevelopmentPlanner()
            goal = planner.build_goals([
                opportunity(
                    opportunity_id="opportunity-1111111111111111",
                    target="app/ai/demo.py",
                )
            ])[0]
            store.save_goal(goal)
            restored = StrategicDevelopmentStore(directory)
            runtime = restored.runtime()
            policy = restored.policy()
            goals = restored.list_goals(limit=10)
        self.assertTrue(runtime["enabled"])
        self.assertFalse(policy["auto_approve"])
        self.assertEqual(len(goals), 1)

    def test_store_history_is_bounded(self) -> None:
        with TemporaryDirectory() as directory:
            store = StrategicDevelopmentStore(directory, max_history=50)
            for index in range(70):
                store.record_history({
                    "status": f"CYCLE-{index}",
                    "success": True,
                })
            history = store.history(limit=100)
        self.assertEqual(len(history), 50)
        self.assertEqual(history[0]["status"], "CYCLE-69")


class B57PlannerTests(unittest.TestCase):

    def setUp(self) -> None:
        self.planner = StrategicDevelopmentPlanner()

    def test_planner_groups_same_subsystem_and_issue_type(self) -> None:
        goals = self.planner.build_goals([
            opportunity(
                opportunity_id="opportunity-1111111111111111",
                target="app/ai/software_engineer/a.py",
            ),
            opportunity(
                opportunity_id="opportunity-2222222222222222",
                target="app/ai/software_engineer/b.py",
            ),
        ])
        self.assertEqual(len(goals), 1)
        self.assertEqual(goals[0].total_count, 2)
        self.assertEqual(goals[0].subsystem, "app/ai/software_engineer")

    def test_planner_separates_issue_types(self) -> None:
        goals = self.planner.build_goals([
            opportunity(
                opportunity_id="opportunity-1111111111111111",
                target="app/ai/a.py",
                issue_type="LARGE_MODULE",
            ),
            opportunity(
                opportunity_id="opportunity-2222222222222222",
                target="app/ai/b.py",
                issue_type="LONG_FUNCTION",
            ),
        ])
        self.assertEqual(len(goals), 2)

    def test_planner_preserves_goal_id_for_same_fingerprint(self) -> None:
        source = opportunity(
            opportunity_id="opportunity-1111111111111111",
            target="app/ai/demo.py",
        )
        first = self.planner.build_goals([source])[0]
        second = self.planner.build_goals(
            [source],
            existing_by_fingerprint={
                first.fingerprint: {
                    "goal_id": "strategic-persistent",
                    "created_at": "2026-01-01T00:00:00+00:00",
                }
            },
        )[0]
        self.assertEqual(second.goal_id, "strategic-persistent")
        self.assertEqual(second.created_at, "2026-01-01T00:00:00+00:00")

    def test_planner_selects_safe_high_value_goal(self) -> None:
        goals = self.planner.build_goals([
            opportunity(
                opportunity_id="opportunity-1111111111111111",
                target="app/low/a.py",
                value=20,
                risk=50,
            ),
            opportunity(
                opportunity_id="opportunity-2222222222222222",
                target="app/high/b.py",
                value=80,
                risk=5,
            ),
        ])
        selected = self.planner.select_goal(
            [item.to_dict() for item in goals],
            min_score=0,
            max_risk=65,
            min_confidence=0.3,
        )
        self.assertEqual(selected["subsystem"], "app/high")

    def test_goal_progress_becomes_completed(self) -> None:
        goal = self.planner.build_goals([
            opportunity(
                opportunity_id="opportunity-1111111111111111",
                target="app/ai/demo.py",
                status="COMPLETED",
            )
        ])[0]
        self.assertEqual(goal.status, "COMPLETED")
        self.assertEqual(goal.completed_count, 1)


class B57ServiceTests(unittest.TestCase):

    def setUp(self) -> None:
        self.directory = TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.project_store = ProjectIntelligenceStore(self.root)
        self.pi = MagicMock()
        self.pi.store = self.project_store
        self.pi.ranker = ProjectOpportunityRanker()
        self.pi.reconcile.return_value = {
            "success": True,
            "status": "PROJECT_INTELLIGENCE_RECONCILED",
        }
        self.b56 = MagicMock()
        self.store = StrategicDevelopmentStore(self.root)
        self.service = StrategicDevelopmentService(
            self.root,
            project_intelligence=self.pi,
            self_directed=self.b56,
            store=self.store,
        )

    def tearDown(self) -> None:
        self.directory.cleanup()

    def add_two_goals(self) -> None:
        self.project_store.save_opportunity(opportunity(
            opportunity_id="opportunity-1111111111111111",
            target="app/ai/a.py",
            value=30,
            risk=30,
        ))
        self.project_store.save_opportunity(opportunity(
            opportunity_id="opportunity-2222222222222222",
            target="app/core/b.py",
            value=80,
            risk=5,
        ))

    def test_refresh_builds_persistent_roadmap(self) -> None:
        self.add_two_goals()
        result = self.service.refresh()
        self.assertEqual(
            result["status"],
            "STRATEGIC_DEVELOPMENT_ROADMAP_REFRESHED",
        )
        self.assertEqual(self.store.summary()["total"], 2)
        restored = StrategicDevelopmentStore(self.root)
        self.assertEqual(restored.summary()["total"], 2)

    def test_select_goal_updates_active_goal(self) -> None:
        self.add_two_goals()
        self.service.refresh()
        result = self.service.select_goal()
        self.assertEqual(
            result["status"],
            "STRATEGIC_DEVELOPMENT_GOAL_SELECTED",
        )
        self.assertEqual(
            result["selected"]["subsystem"],
            "app/core",
        )
        self.assertTrue(self.store.runtime()["active_goal_id"])

    def test_recommendation_stays_inside_selected_goal(self) -> None:
        self.add_two_goals()
        self.store.update_runtime({"enabled": True})
        self.service.refresh()
        self.service.select_goal()
        result = self.service.recommend_opportunity(
            refresh_if_due=False
        )
        self.assertEqual(
            result["recommendation"]["opportunity_id"],
            "opportunity-2222222222222222",
        )

    def test_disabled_service_does_not_recommend(self) -> None:
        result = self.service.recommend_opportunity()
        self.assertEqual(result["status"], "STRATEGIC_DEVELOPMENT_DISABLED")
        self.assertEqual(result["recommendation"], {})

    def test_start_enables_b56_and_never_auto_approves(self) -> None:
        fake_thread = MagicMock()
        fake_thread.is_alive.return_value = True
        with patch(
            "app.ai.software_engineer.strategic_development_service.threading.Thread",
            return_value=fake_thread,
        ):
            result = self.service.start_background()
        self.assertEqual(
            result["status"],
            "STRATEGIC_DEVELOPMENT_SUPERVISOR_STARTED",
        )
        self.b56.start_background.assert_called_once_with()
        self.assertFalse(self.store.policy()["auto_approve"])
        self.assertTrue(self.store.runtime()["enabled"])

    def test_pause_and_stop_delegate_to_b56(self) -> None:
        self.service.pause()
        self.b56.pause.assert_called_once_with()
        self.service.stop_background()
        self.b56.stop_background.assert_called_once_with()
        self.assertFalse(self.store.runtime()["enabled"])

    def test_run_cycle_refreshes_selects_and_recommends(self) -> None:
        self.add_two_goals()
        self.store.update_runtime({"enabled": True})
        result = self.service.run_cycle()
        self.assertEqual(
            result["status"],
            "STRATEGIC_DEVELOPMENT_CYCLE_COMPLETED",
        )
        self.assertTrue(result["selected"])
        self.assertTrue(result["recommendation"])


class B57IntegrationTests(unittest.TestCase):

    def test_b56_dispatches_b57_recommendation(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            project_store = ProjectIntelligenceStore(root)
            pi = MagicMock()
            pi.store = project_store
            pi.reconcile.return_value = {"success": True}
            pi.scan_project.return_value = {
                "success": True,
                "status": "PROJECT_INTELLIGENCE_SCAN_COMPLETED",
            }
            pi.dispatch_opportunity.return_value = {
                "success": True,
                "status": "PROJECT_INTELLIGENCE_JOB_DISPATCHED",
                "job_id": "longrun-b57",
            }
            pi.dispatch_best.return_value = {
                "success": True,
                "job_id": "longrun-fallback",
            }
            store = SelfDirectedDevelopmentStore(root)
            store.update_policy({"auto_dispatch": True})
            store.update_runtime({
                "enabled": True,
                "paused": False,
                "dispatch_day": datetime.now(timezone.utc).date().isoformat(),
            })
            service = SelfDirectedDevelopmentService(
                root,
                project_intelligence=pi,
                store=store,
            )
            strategic = MagicMock()
            strategic.is_enabled.return_value = True
            strategic.recommend_opportunity.return_value = {
                "status": "STRATEGIC_DEVELOPMENT_RECOMMENDATION_READY",
                "selected": {"goal_id": "strategic-one"},
                "recommendation": {
                    "opportunity_id": "opportunity-1111111111111111"
                },
            }
            service.strategic_development_service = strategic
            result = service.run_cycle()
        self.assertEqual(result["status"], "SELF_DIRECTED_JOB_DISPATCHED")
        pi.dispatch_opportunity.assert_called_once_with(
            "opportunity-1111111111111111",
            force=True,
        )
        pi.dispatch_best.assert_not_called()

    def test_project_intelligence_dispatch_specific_is_safe(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            store = ProjectIntelligenceStore(root)
            item = store.save_opportunity(opportunity(
                opportunity_id="opportunity-1111111111111111",
                target="app/demo.py",
            ))
            long_running = MagicMock()
            long_running.enqueue.return_value = {
                "success": True,
                "job_id": "longrun-specific",
                "job": {"job_id": "longrun-specific"},
            }
            long_running.store.get_job.return_value = None
            service = ProjectIntelligenceService(
                root,
                long_running_service=long_running,
                store=store,
            )
            with patch.object(
                service,
                "_execution_targets",
                return_value=["app/demo.py", "tests/test_demo.py"],
            ):
                result = service.dispatch_opportunity(
                    item["opportunity_id"],
                    force=True,
                )
        self.assertEqual(
            result["status"],
            "PROJECT_INTELLIGENCE_JOB_DISPATCHED",
        )
        context = long_running.enqueue.call_args.kwargs["context"]
        self.assertFalse(context["auto_approve"])
        self.assertEqual(context["autonomy_targets"][0], "app/demo.py")

    def test_bootstrap_attaches_b57_to_b55_and_b56(self) -> None:
        with TemporaryDirectory() as directory:
            pi = MagicMock()
            pi.start_if_enabled.return_value = {}
            pi.store = ProjectIntelligenceStore(directory)
            pi.ranker = ProjectOpportunityRanker()
            b56 = MagicMock()
            b56.start_if_enabled.return_value = {}
            controller = SimpleNamespace(
                project_root=directory,
                project_intelligence_service=pi,
                self_directed_development_service=b56,
            )
            service = bootstrap_strategic_development(controller)
        self.assertIs(controller.strategic_development_service, service)
        self.assertIs(pi.strategic_development_service, service)
        self.assertIs(b56.strategic_development_service, service)


class B57RoutingFormattingTests(unittest.TestCase):

    def test_router_routes_status_and_start(self) -> None:
        service = MagicMock()
        service.start_if_enabled.return_value = {}
        service.status.return_value = {
            "success": True,
            "status": "STRATEGIC_DEVELOPMENT_STATUS",
            "operation": "strategic_development",
        }
        service.start_background.return_value = {
            "success": True,
            "status": "STRATEGIC_DEVELOPMENT_SUPERVISOR_STARTED",
            "operation": "strategic_development",
        }
        controller = SimpleNamespace(
            _normalize=lambda value: " ".join(value.casefold().split()),
        )
        router = SoftwareEngineerStrategicDevelopmentRouter()
        with patch(
            "app.ai.software_engineer.software_engineer_strategic_development_router.bootstrap_strategic_development",
            return_value=service,
        ):
            status = router.try_handle(
                controller,
                command="Pokaż status rozwoju strategicznego",
                objective="",
                context={},
            )
            started = router.try_handle(
                controller,
                command="Uruchom rozwój strategiczny",
                objective="",
                context={},
            )
        self.assertEqual(status["status"], "STRATEGIC_DEVELOPMENT_STATUS")
        self.assertEqual(
            started["status"],
            "STRATEGIC_DEVELOPMENT_SUPERVISOR_STARTED",
        )

    def test_formatter_reports_safety_and_roadmap(self) -> None:
        text = format_strategic_development_response({
            "status": "STRATEGIC_DEVELOPMENT_STATUS",
            "operation": "strategic_development",
            "runtime": {
                "enabled": True,
                "phase": "READY",
                "cycles_completed": 2,
                "active_goal_id": "strategic-one",
            },
            "policy": StrategicDevelopmentPolicy().to_dict(),
            "summary": {
                "total": 2,
                "pending": 1,
                "active": 1,
                "completed": 0,
                "partial": 0,
                "blocked": 0,
            },
            "project_summary": {"total": 10, "pending": 8, "active": 1},
            "selected": {
                "goal_id": "strategic-one",
                "title": "Large Module: app/ai",
                "subsystem": "app/ai",
                "issue_type": "LARGE_MODULE",
                "completed_count": 0,
                "active_count": 1,
                "pending_count": 2,
                "failed_count": 0,
            },
            "report_path": "data/autodev/strategic_development.json",
        })
        self.assertIn("Rozwój strategiczny B57", text)
        self.assertIn("Roadmapa B57", text)
        self.assertIn("auto-approve NIE", text)

    def test_brain_formatter_routes_b57(self) -> None:
        formatter = BrainResponseFormatter()
        text = formatter._format_software_engineer_response({
            "status": "STRATEGIC_DEVELOPMENT_STATUS",
            "operation": "strategic_development",
            "runtime": {},
            "policy": {},
            "summary": {},
        })
        self.assertIn("Rozwój strategiczny B57", text)

    def test_status_is_read_only_but_start_requires_confirmation(self) -> None:
        self.assertTrue(
            is_read_only_learning_command(
                "Pokaż status rozwoju strategicznego"
            )
        )
        self.assertFalse(
            is_read_only_learning_command(
                "Uruchom rozwój strategiczny"
            )
        )

    def test_router_and_brain_integration_stay_auditable(self) -> None:
        root = Path(__file__).resolve().parents[1]
        router = (
            root
            / "app/ai/software_engineer/software_engineer_advanced_change_router.py"
        )
        brain = root / "app/ai/brain.py"
        self.assertLess(len(router.read_text(encoding="utf-8").splitlines()), 360)
        brain_source = brain.read_text(encoding="utf-8")
        self.assertIn("bootstrap_strategic_development", brain_source)
        self.assertIn("self.strategic_development_service", brain_source)


if __name__ == "__main__":
    unittest.main()
