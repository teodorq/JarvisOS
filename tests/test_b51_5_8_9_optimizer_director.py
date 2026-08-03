"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations

from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from app.ai.brain_response_formatter import BrainResponseFormatter
from app.ai.software_engineer.autonomous_campaign_director import (
    AutonomousCampaignDirector,
)
from app.ai.software_engineer.autonomous_software_engineer import (
    AutonomousSoftwareEngineerController,
)
from app.ai.software_engineer.multi_campaign_planner import (
    MultiCampaignPlanner,
)
from app.ai.software_engineer.multi_campaign_store import (
    MultiCampaignStore,
)
from app.ai.software_engineer.multi_campaign_workflow import (
    MultiCampaignWorkflow,
)
from app.ai.software_engineer.portfolio_director_store import (
    PortfolioDirectorStore,
)
from app.ai.software_engineer.portfolio_optimizer import (
    PortfolioOptimizer,
)
from app.ai.software_engineer.software_engineer_campaign_router import (
    SoftwareEngineerCampaignRouter,
)
from app.ai.software_engineer.software_engineer_portfolio_router import (
    SoftwareEngineerPortfolioRouter,
)
from app.autodev.execution_result import ExecutionResult


class CampaignWorkflowStub:

    def __init__(self) -> None:
        self.run_results: dict[str, list[dict] | dict] = {}
        self.resume_results: dict[str, list[dict] | dict] = {}
        self.existing: dict[str, dict] = {}
        self.run_calls: list[str] = []
        self.resume_calls: list[str] = []
        self.rollback_calls: list[str] = []

    @staticmethod
    def _next(value, default: dict) -> dict:
        if isinstance(value, list):
            return dict(value.pop(0) if value else default)
        if isinstance(value, dict):
            return dict(value)
        return dict(default)

    def run(self, objective: str, *, campaign_id: str, **kwargs) -> dict:
        self.run_calls.append(campaign_id)
        result = self._next(
            self.run_results.get(campaign_id),
            {
                "success": True,
                "status": "CAMPAIGN_COMPLETED",
                "errors": [],
            },
        )
        self.existing[campaign_id] = dict(result)
        return result

    def resume(self, campaign_id: str, **kwargs) -> dict:
        self.resume_calls.append(campaign_id)
        result = self._next(
            self.resume_results.get(campaign_id),
            {
                "success": True,
                "status": "CAMPAIGN_COMPLETED",
                "errors": [],
            },
        )
        self.existing[campaign_id] = dict(result)
        return result

    def rollback(self, campaign_id: str) -> dict:
        self.rollback_calls.append(campaign_id)
        return {
            "success": True,
            "status": "CAMPAIGN_ROLLED_BACK",
            "errors": [],
        }

    def get_campaign(self, campaign_id: str):
        return self.existing.get(campaign_id)


class ValidatorStub:

    def __init__(self, success: bool = True) -> None:
        self.success = success
        self.calls: list[dict] = []

    def run_test_suite(self, *, changed_files, full_suite):
        self.calls.append(
            {
                "changed_files": list(changed_files),
                "full_suite": bool(full_suite),
            }
        )
        return ExecutionResult(
            success=self.success,
            step_name="run_test_suite",
            message="OK" if self.success else "FAIL",
            errors=[] if self.success else ["validation failed"],
        )


class B51589OptimizerDirectorTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for relative in (
            "app/ai/a.py",
            "app/autodev/b.py",
            "app/gui/c.py",
            "app/core/d.py",
            "app/memory/e.py",
            "app/automation/f.py",
            "app/browser/g.py",
            "app/vision/h.py",
            "app/agent/i.py",
            "app/skills/j.py",
            "app/research/k.py",
            "app/desktop/l.py",
        ):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("VALUE = 1\n", encoding="utf-8")

    def tearDown(self) -> None:
        self.temp.cleanup()

    @staticmethod
    def stage(stage_id: str, first: str, second: str) -> dict:
        return {
            "stage_id": stage_id,
            "objective": f"Etap {stage_id}",
            "replacements": {
                first: "VALUE = 2\n",
                second: "VALUE = 2\n",
            },
        }

    def campaigns(self) -> list[dict]:
        return [
            {
                "campaign_id": "fast-value",
                "objective": "Szybka wartościowa zmiana",
                "priority": "NORMAL",
                "estimated_roi": 9,
                "estimated_risk": 2,
                "estimated_minutes": 20,
                "confidence": 0.9,
                "stages": [
                    self.stage("fast-1", "app/ai/a.py", "app/autodev/b.py"),
                    self.stage("fast-2", "app/gui/c.py", "app/core/d.py"),
                ],
            },
            {
                "campaign_id": "slow-risky",
                "objective": "Długa ryzykowna zmiana",
                "priority": "CRITICAL",
                "estimated_roi": 3,
                "estimated_risk": 9,
                "estimated_minutes": 240,
                "confidence": 0.3,
                "stages": [
                    self.stage("slow-1", "app/memory/e.py", "app/automation/f.py"),
                    self.stage("slow-2", "app/browser/g.py", "app/vision/h.py"),
                ],
            },
            {
                "campaign_id": "balanced",
                "objective": "Zrównoważona zmiana",
                "priority": "HIGH",
                "estimated_roi": 7,
                "estimated_risk": 4,
                "estimated_minutes": 60,
                "confidence": 0.7,
                "stages": [
                    self.stage("balanced-1", "app/agent/i.py", "app/skills/j.py"),
                    self.stage("balanced-2", "app/research/k.py", "app/desktop/l.py"),
                ],
            },
        ]

    def planner(self) -> MultiCampaignPlanner:
        return MultiCampaignPlanner(self.root)

    def workflow(
        self,
        *,
        stub: CampaignWorkflowStub | None = None,
        validator: ValidatorStub | None = None,
    ) -> MultiCampaignWorkflow:
        return MultiCampaignWorkflow(
            self.root,
            campaign_workflow=stub or CampaignWorkflowStub(),
            validator=validator or ValidatorStub(),
        )

    def planned(
        self,
        *,
        portfolio_id: str = "optimized",
        campaigns: list[dict] | None = None,
    ):
        return self.planner().plan(
            "Portfolio autonomicznego rozwoju",
            campaigns or self.campaigns(),
            portfolio_id=portfolio_id,
        )

    def test_planner_persists_roi_risk_time_and_confidence(self) -> None:
        item = self.planned().campaign("fast-value")
        self.assertEqual(item.metadata["estimated_roi"], 9.0)
        self.assertEqual(item.metadata["estimated_risk"], 2.0)
        self.assertEqual(item.metadata["estimated_minutes"], 20.0)
        self.assertEqual(item.metadata["confidence"], 0.9)

    def test_optimizer_prefers_high_roi_low_risk_short_campaign(self) -> None:
        result = PortfolioOptimizer(self.root).optimize(self.planned())
        self.assertEqual(result["optimized_order"][0], "fast-value")
        self.assertGreater(
            result["campaign_scores"]["fast-value"]["score"],
            result["campaign_scores"]["slow-risky"]["score"],
        )

    def test_optimizer_scores_are_bounded(self) -> None:
        result = PortfolioOptimizer(self.root).optimize(self.planned())
        self.assertTrue(
            all(
                0 <= value["score"] <= 100
                for value in result["campaign_scores"].values()
            )
        )

    def test_optimizer_respects_dependency_order(self) -> None:
        campaigns = self.campaigns()
        campaigns[0]["depends_on"] = ["slow-risky"]
        portfolio = self.planned(campaigns=campaigns)
        result = PortfolioOptimizer(self.root).optimize(portfolio)
        self.assertLess(
            result["optimized_order"].index("slow-risky"),
            result["optimized_order"].index("fast-value"),
        )

    def test_optimizer_respects_time_budget(self) -> None:
        result = PortfolioOptimizer(self.root).optimize(
            self.planned(),
            constraints={"max_total_minutes": 70},
        )
        self.assertIn("fast-value", result["selected_campaign_ids"])
        self.assertLessEqual(result["estimated_minutes"], 70)
        self.assertTrue(
            any(
                item["reason"] == "TIME_BUDGET_EXCEEDED"
                for item in result["deferred_campaigns"]
            )
        )

    def test_optimizer_respects_risk_limit(self) -> None:
        result = PortfolioOptimizer(self.root).optimize(
            self.planned(),
            constraints={"max_risk": 5},
        )
        self.assertNotIn("slow-risky", result["selected_campaign_ids"])
        deferred = {
            item["campaign_id"]: item["reason"]
            for item in result["deferred_campaigns"]
        }
        self.assertEqual(deferred["slow-risky"], "RISK_ABOVE_LIMIT")

    def test_optimizer_respects_minimum_score(self) -> None:
        result = PortfolioOptimizer(self.root).optimize(
            self.planned(),
            constraints={"min_score": 80},
        )
        self.assertTrue(
            all(
                result["campaign_scores"][campaign_id]["score"] >= 80
                for campaign_id in result["selected_campaign_ids"]
            )
        )

    def test_optimizer_apply_updates_order_and_metadata(self) -> None:
        portfolio = self.planned()
        result = PortfolioOptimizer(self.root).optimize(portfolio, apply=True)
        self.assertEqual(portfolio.execution_order, result["optimized_order"])
        self.assertIn("optimization", portfolio.metadata)
        self.assertIn("optimization", portfolio.campaign("fast-value").metadata)

    def test_success_history_boosts_campaign_score(self) -> None:
        store = MultiCampaignStore(self.root)
        historical = self.planned(portfolio_id="history-success")
        historical.campaign("balanced").status = "COMPLETED"
        historical.campaign("fast-value").status = "FAILED"
        store.save(historical)
        current = self.planned(portfolio_id="history-current")
        result = PortfolioOptimizer(self.root, store=store).optimize(current)
        self.assertGreater(
            result["campaign_scores"]["balanced"]["history_score"],
            result["campaign_scores"]["fast-value"]["history_score"],
        )

    def test_rollback_history_penalizes_campaign(self) -> None:
        store = MultiCampaignStore(self.root)
        historical = self.planned(portfolio_id="history-rollback")
        historical.campaign("balanced").status = "ROLLED_BACK"
        historical.campaign("balanced").result = {
            "status": "CAMPAIGN_ROLLED_BACK"
        }
        store.save(historical)
        current = self.planned(portfolio_id="history-current-2")
        result = PortfolioOptimizer(self.root, store=store).optimize(current)
        metric = result["campaign_scores"]["balanced"]
        self.assertEqual(metric["history_rollbacks"], 1)
        self.assertLess(metric["history_score"], 50)

    def test_optimizer_custom_weights_are_normalized(self) -> None:
        result = PortfolioOptimizer(self.root).optimize(
            self.planned(),
            constraints={"weights": {"roi": 10, "risk": 0}},
        )
        self.assertAlmostEqual(sum(result["weights"].values()), 1.0)

    def test_processed_limit_counts_failed_campaign_attempt(self) -> None:
        stub = CampaignWorkflowStub()
        stub.run_results["fast-value"] = {
            "success": False,
            "status": "CAMPAIGN_STAGE_FAILED",
            "errors": ["failure"],
        }
        workflow = self.workflow(stub=stub)
        result = workflow.run(
            "Portfolio",
            campaigns=self.campaigns(),
            portfolio_id="failed-limit",
            continue_on_failure=True,
            auto_rollback=False,
            rollback_completed_on_failure=False,
            max_campaigns_per_run=1,
        )
        self.assertEqual(result["status"], "MULTI_CAMPAIGN_PAUSED")
        self.assertEqual(len(stub.run_calls), 1)

    def test_director_completes_portfolio_one_campaign_per_cycle(self) -> None:
        stub = CampaignWorkflowStub()
        workflow = self.workflow(stub=stub)
        workflow.run(
            "Portfolio",
            campaigns=self.campaigns(),
            portfolio_id="director-complete",
            auto_execute=False,
        )
        result = AutonomousCampaignDirector(
            self.root,
            workflow=workflow,
        ).direct("director-complete")
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "MULTI_CAMPAIGN_COMPLETED")
        self.assertEqual(result["director_run"]["cycles"], 3)
        self.assertEqual(len(stub.run_calls), 3)

    def test_director_reoptimizes_before_each_cycle(self) -> None:
        workflow = self.workflow()
        workflow.run(
            "Portfolio",
            campaigns=self.campaigns(),
            portfolio_id="director-decisions",
            auto_execute=False,
        )
        result = AutonomousCampaignDirector(
            self.root,
            workflow=workflow,
        ).direct("director-decisions")
        decisions = result["director_run"]["decisions"]
        self.assertEqual(len(decisions), result["director_run"]["cycles"])
        self.assertTrue(all("optimized_order" in item for item in decisions))

    def test_director_pauses_when_constraints_select_nothing(self) -> None:
        workflow = self.workflow()
        workflow.run(
            "Portfolio",
            campaigns=self.campaigns(),
            portfolio_id="director-budget",
            auto_execute=False,
        )
        result = AutonomousCampaignDirector(
            self.root,
            workflow=workflow,
        ).direct(
            "director-budget",
            constraints={"min_score": 100},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "CAMPAIGN_DIRECTOR_PAUSED_CONSTRAINTS")

    def test_director_retries_failed_campaign(self) -> None:
        stub = CampaignWorkflowStub()
        stub.run_results["fast-value"] = {
            "success": False,
            "status": "CAMPAIGN_STAGE_FAILED",
            "errors": ["temporary failure"],
        }
        stub.resume_results["fast-value"] = {
            "success": True,
            "status": "CAMPAIGN_COMPLETED",
            "errors": [],
        }
        workflow = self.workflow(stub=stub)
        workflow.run(
            "Portfolio",
            campaigns=self.campaigns(),
            portfolio_id="director-retry",
            auto_execute=False,
        )
        result = AutonomousCampaignDirector(
            self.root,
            workflow=workflow,
        ).direct(
            "director-retry",
            max_retries_per_campaign=1,
            max_failures=3,
        )
        self.assertEqual(result["status"], "MULTI_CAMPAIGN_COMPLETED")
        self.assertEqual(result["director_run"]["retries"], 1)
        self.assertIn("fast-value", stub.resume_calls)

    def test_director_stops_at_failure_limit(self) -> None:
        stub = CampaignWorkflowStub()
        stub.run_results["fast-value"] = {
            "success": False,
            "status": "CAMPAIGN_STAGE_FAILED",
            "errors": ["permanent failure"],
        }
        workflow = self.workflow(stub=stub)
        workflow.run(
            "Portfolio",
            campaigns=self.campaigns(),
            portfolio_id="director-failure-limit",
            auto_execute=False,
        )
        result = AutonomousCampaignDirector(
            self.root,
            workflow=workflow,
        ).direct(
            "director-failure-limit",
            max_retries_per_campaign=0,
            max_failures=1,
        )
        self.assertFalse(result["success"])
        self.assertEqual(
            result["status"],
            "CAMPAIGN_DIRECTOR_STOPPED_FAILURE_LIMIT",
        )

    def test_director_can_rollback_when_failure_limit_is_reached(self) -> None:
        stub = CampaignWorkflowStub()
        stub.run_results["fast-value"] = {
            "success": True,
            "status": "CAMPAIGN_COMPLETED",
            "errors": [],
        }
        stub.run_results["balanced"] = {
            "success": False,
            "status": "CAMPAIGN_STAGE_FAILED",
            "errors": ["failure"],
        }
        workflow = self.workflow(stub=stub)
        workflow.run(
            "Portfolio",
            campaigns=self.campaigns(),
            portfolio_id="director-rollback",
            auto_execute=False,
        )
        result = AutonomousCampaignDirector(
            self.root,
            workflow=workflow,
        ).direct(
            "director-rollback",
            max_retries_per_campaign=0,
            max_failures=1,
            rollback_on_stop=True,
        )
        self.assertEqual(
            result["status"],
            "CAMPAIGN_DIRECTOR_STOPPED_AND_ROLLED_BACK",
        )
        self.assertTrue(stub.rollback_calls)

    def test_director_store_persists_status_and_recent_runs(self) -> None:
        store = PortfolioDirectorStore(self.root, max_records=10)
        store.save(
            {
                "run_id": "run-1",
                "portfolio_id": "portfolio-1",
                "status": "DONE",
            }
        )
        self.assertEqual(store.get("run-1")["status"], "DONE")
        self.assertEqual(store.latest_for_portfolio("portfolio-1")["run_id"], "run-1")
        self.assertEqual(store.list_recent(limit=1)[0]["run_id"], "run-1")

    def test_optimizer_router_updates_existing_portfolio(self) -> None:
        workflow = self.workflow()
        workflow.run(
            "Portfolio",
            campaigns=self.campaigns(),
            portfolio_id="router-optimize",
            auto_execute=False,
        )
        controller = SimpleNamespace(
            project_root=self.root,
            multi_campaign_workflow=workflow,
            _normalize=lambda value: str(value).casefold(),
        )
        result = SoftwareEngineerPortfolioRouter().try_handle(
            controller,
            command="optymalizuj portfolio kampanii",
            objective="Portfolio",
            context={
                "operation": "multi_campaign",
                "portfolio_action": "optimize",
                "portfolio_id": "router-optimize",
                "optimization_constraints": {"max_risk": 5},
            },
        )
        self.assertEqual(result["status"], "PORTFOLIO_OPTIMIZED")
        self.assertIn("optimization", result)

    def test_director_router_starts_plans_and_executes_portfolio(self) -> None:
        stub = CampaignWorkflowStub()
        workflow = self.workflow(stub=stub)
        controller = SimpleNamespace(
            project_root=self.root,
            multi_campaign_workflow=workflow,
            _normalize=lambda value: str(value).casefold(),
        )
        result = SoftwareEngineerCampaignRouter().try_handle(
            controller,
            command="uruchom autonomicznego dyrektora kampanii",
            objective="Portfolio",
            context={
                "operation": "multi_campaign",
                "portfolio_action": "director",
                "portfolio_id": "router-director",
                "portfolio_campaigns": self.campaigns(),
            },
        )
        self.assertEqual(result["status"], "MULTI_CAMPAIGN_COMPLETED")
        self.assertIn("director_run", result)

    def test_director_status_and_recent_are_routed(self) -> None:
        workflow = self.workflow()
        workflow.run(
            "Portfolio",
            campaigns=self.campaigns(),
            portfolio_id="router-director-status",
            auto_execute=False,
        )
        controller = SimpleNamespace(
            project_root=self.root,
            multi_campaign_workflow=workflow,
            _normalize=lambda value: str(value).casefold(),
        )
        router = SoftwareEngineerPortfolioRouter()
        completed = router.try_handle(
            controller,
            command="campaign director",
            objective="Portfolio",
            context={
                "operation": "multi_campaign",
                "portfolio_action": "director",
                "portfolio_id": "router-director-status",
            },
        )
        status = router.try_handle(
            controller,
            command="status dyrektora kampanii",
            objective="Portfolio",
            context={
                "operation": "multi_campaign",
                "portfolio_action": "director_status",
                "director_run_id": completed["director_run"]["run_id"],
            },
        )
        recent = router.try_handle(
            controller,
            command="historia dyrektora kampanii",
            objective="Portfolio",
            context={
                "operation": "multi_campaign",
                "portfolio_action": "director_recent",
            },
        )
        self.assertTrue(status["success"])
        self.assertEqual(recent["status"], "CAMPAIGN_DIRECTOR_RECENT")
        self.assertTrue(recent["director_runs"])

    def test_formatter_reports_optimizer_and_director(self) -> None:
        response = {
            "success": True,
            "status": "CAMPAIGN_DIRECTOR_PAUSED_CONSTRAINTS",
            "operation": "multi_campaign",
            "portfolio_id": "format-director",
            "portfolio": {
                "campaigns": [{}, {}],
                "completed_campaign_ids": [],
                "metadata": {},
            },
            "optimization": {
                "average_score": 72.5,
                "selected_campaign_ids": ["fast-value"],
                "deferred_campaigns": [{"campaign_id": "slow-risky"}],
                "estimated_minutes": 20,
            },
            "director_run": {
                "run_id": "director-1",
                "cycles": 2,
                "retries": 1,
            },
            "errors": [],
        }
        text = BrainResponseFormatter()._format_software_engineer_response(response)
        self.assertIn("Wynik optymalizacji: 72.5/100", text)
        self.assertIn("Dyrektor kampanii: director-1", text)
        self.assertIn("Retry dyrektora: 1", text)

    def test_director_recovers_blocked_dependents_after_retry(self) -> None:
        campaigns = self.campaigns()[:2]
        campaigns[1]["depends_on"] = ["fast-value"]
        stub = CampaignWorkflowStub()
        stub.run_results["fast-value"] = {
            "success": False,
            "status": "CAMPAIGN_STAGE_FAILED",
            "errors": ["temporary"],
        }
        stub.resume_results["fast-value"] = {
            "success": True,
            "status": "CAMPAIGN_COMPLETED",
            "errors": [],
        }
        workflow = self.workflow(stub=stub)
        workflow.run(
            "Portfolio",
            campaigns=campaigns,
            portfolio_id="recover-blocked",
            auto_execute=False,
        )
        result = AutonomousCampaignDirector(
            self.root,
            workflow=workflow,
        ).direct(
            "recover-blocked",
            max_retries_per_campaign=1,
            max_failures=3,
        )
        self.assertEqual(result["status"], "MULTI_CAMPAIGN_COMPLETED")
        self.assertIn("slow-risky", stub.run_calls)

    def test_controller_detects_optimizer_and_director_commands(self) -> None:
        self.assertTrue(
            AutonomousSoftwareEngineerController.can_handle(
                "optymalizuj portfolio autonomicznie"
            )
        )
        self.assertTrue(
            AutonomousSoftwareEngineerController.can_handle(
                "uruchom dyrektora kampanii"
            )
        )

    def test_controller_remains_below_audit_limit(self) -> None:
        module_path = Path(
            AutonomousSoftwareEngineerController.__module__.replace(".", "/") + ".py"
        )
        controller_path = Path(__file__).resolve().parents[1] / module_path
        self.assertLess(
            len(controller_path.read_text(encoding="utf-8").splitlines()),
            440,
        )


if __name__ == "__main__":
    unittest.main()
