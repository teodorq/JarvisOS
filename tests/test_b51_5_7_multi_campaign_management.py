from __future__ import annotations

from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from app.ai.brain_response_formatter import BrainResponseFormatter
from app.ai.software_engineer.autonomous_software_engineer import (
    AutonomousSoftwareEngineerController,
)
from app.ai.software_engineer.multi_campaign_models import (
    MultiCampaignPortfolio,
)
from app.ai.software_engineer.multi_campaign_planner import (
    MultiCampaignPlanner,
)
from app.ai.software_engineer.multi_campaign_scheduler import (
    MultiCampaignScheduler,
)
from app.ai.software_engineer.multi_campaign_store import (
    MultiCampaignStore,
)
from app.ai.software_engineer.multi_campaign_workflow import (
    MultiCampaignWorkflow,
)
from app.ai.software_engineer.software_engineer_campaign_router import (
    SoftwareEngineerCampaignRouter,
)
from app.autodev.execution_result import ExecutionResult


class CampaignWorkflowStub:

    def __init__(self) -> None:
        self.run_results: dict[str, dict] = {}
        self.resume_results: dict[str, dict] = {}
        self.existing: dict[str, dict] = {}
        self.run_calls: list[str] = []
        self.resume_calls: list[str] = []
        self.rollback_calls: list[str] = []

    def run(self, objective: str, *, campaign_id: str, **kwargs) -> dict:
        self.run_calls.append(campaign_id)
        result = dict(
            self.run_results.get(
                campaign_id,
                {
                    "success": True,
                    "status": "CAMPAIGN_COMPLETED",
                    "errors": [],
                },
            )
        )
        self.existing[campaign_id] = dict(result)
        return result

    def resume(self, campaign_id: str, **kwargs) -> dict:
        self.resume_calls.append(campaign_id)
        result = dict(
            self.resume_results.get(
                campaign_id,
                {
                    "success": True,
                    "status": "CAMPAIGN_COMPLETED",
                    "errors": [],
                },
            )
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
            errors=[] if self.success else ["final validation failed"],
        )


class B5157MultiCampaignManagementTests(unittest.TestCase):

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
                "campaign_id": "normal",
                "objective": "Normalna kampania",
                "priority": "NORMAL",
                "stages": [
                    self.stage("normal-1", "app/ai/a.py", "app/autodev/b.py"),
                    self.stage("normal-2", "app/gui/c.py", "app/core/d.py"),
                ],
            },
            {
                "campaign_id": "critical",
                "objective": "Krytyczna kampania",
                "priority": "CRITICAL",
                "stages": [
                    self.stage("critical-1", "app/memory/e.py", "app/automation/f.py"),
                    self.stage("critical-2", "app/browser/g.py", "app/vision/h.py"),
                ],
            },
        ]

    def workflow(self, *, stub=None, validator=None) -> MultiCampaignWorkflow:
        return MultiCampaignWorkflow(
            self.root,
            campaign_workflow=stub or CampaignWorkflowStub(),
            validator=validator or ValidatorStub(),
        )

    def test_planner_orders_ready_campaigns_by_priority(self) -> None:
        portfolio = MultiCampaignPlanner(self.root).plan(
            "Portfolio",
            self.campaigns(),
            portfolio_id="priority-order",
        )
        self.assertEqual(portfolio.execution_order, ["critical", "normal"])
        self.assertEqual(portfolio.metadata["campaign_count"], 2)

    def test_dependency_overrides_higher_priority(self) -> None:
        campaigns = self.campaigns()
        campaigns[1]["depends_on"] = ["normal"]
        portfolio = MultiCampaignPlanner(self.root).plan("Portfolio", campaigns)
        self.assertEqual(portfolio.execution_order, ["normal", "critical"])

    def test_planner_rejects_dependency_cycle(self) -> None:
        campaigns = self.campaigns()
        campaigns[0]["depends_on"] = ["critical"]
        campaigns[1]["depends_on"] = ["normal"]
        with self.assertRaises(ValueError):
            MultiCampaignPlanner(self.root).plan("Portfolio", campaigns)

    def test_planner_rejects_unknown_dependency(self) -> None:
        campaigns = self.campaigns()
        campaigns[0]["depends_on"] = ["missing"]
        with self.assertRaises(ValueError):
            MultiCampaignPlanner(self.root).plan("Portfolio", campaigns)

    def test_planner_rejects_duplicate_campaign_ids(self) -> None:
        campaigns = self.campaigns()
        campaigns[1]["campaign_id"] = "normal"
        with self.assertRaises(ValueError):
            MultiCampaignPlanner(self.root).plan("Portfolio", campaigns)

    def test_unordered_file_conflict_is_rejected(self) -> None:
        campaigns = self.campaigns()
        campaigns[1]["stages"][0] = self.stage(
            "critical-conflict",
            "app/ai/a.py",
            "app/memory/e.py",
        )
        with self.assertRaises(ValueError):
            MultiCampaignPlanner(self.root).plan("Portfolio", campaigns)

    def test_ordered_file_conflict_is_allowed(self) -> None:
        campaigns = self.campaigns()
        campaigns[1]["depends_on"] = ["normal"]
        campaigns[1]["stages"][0] = self.stage(
            "critical-conflict",
            "app/ai/a.py",
            "app/memory/e.py",
        )
        portfolio = MultiCampaignPlanner(self.root).plan("Portfolio", campaigns)
        self.assertEqual(portfolio.execution_order, ["normal", "critical"])

    def test_model_round_trip_preserves_priority_and_dependencies(self) -> None:
        campaigns = self.campaigns()
        campaigns[1]["depends_on"] = ["normal"]
        portfolio = MultiCampaignPlanner(self.root).plan("Portfolio", campaigns)
        restored = MultiCampaignPortfolio.from_dict(portfolio.to_dict())
        self.assertEqual(restored.execution_order, portfolio.execution_order)
        self.assertEqual(restored.campaign("critical").priority, "CRITICAL")
        self.assertEqual(restored.campaign("critical").depends_on, ["normal"])

    def test_scheduler_marks_failed_dependents_as_blocked(self) -> None:
        campaigns = self.campaigns()
        campaigns[1]["depends_on"] = ["normal"]
        portfolio = MultiCampaignPlanner(self.root).plan("Portfolio", campaigns)
        portfolio.campaign("normal").status = "FAILED"
        blocked = MultiCampaignScheduler().mark_blocked(portfolio)
        self.assertEqual(blocked, ["critical"])
        self.assertEqual(portfolio.campaign("critical").status, "BLOCKED")

    def test_store_persists_and_returns_recent_portfolios(self) -> None:
        store = MultiCampaignStore(self.root, max_records=10)
        portfolio = MultiCampaignPlanner(self.root).plan(
            "Portfolio",
            self.campaigns(),
            portfolio_id="stored",
        )
        store.save(portfolio)
        loaded = store.get("stored")
        self.assertIsNotNone(loaded)
        self.assertEqual(loaded.fingerprint, portfolio.fingerprint)
        self.assertEqual(store.list_recent(limit=1)[0]["portfolio_id"], "stored")

    def test_workflow_executes_campaigns_in_priority_order(self) -> None:
        stub = CampaignWorkflowStub()
        result = self.workflow(stub=stub).run(
            "Portfolio",
            campaigns=self.campaigns(),
            portfolio_id="execute-order",
        )
        self.assertTrue(result["success"])
        self.assertEqual(stub.run_calls, ["critical", "normal"])
        self.assertEqual(result["status"], "MULTI_CAMPAIGN_COMPLETED")

    def test_portfolio_pauses_and_resumes_from_store(self) -> None:
        stub = CampaignWorkflowStub()
        workflow = self.workflow(stub=stub)
        first = workflow.run(
            "Portfolio",
            campaigns=self.campaigns(),
            portfolio_id="pause-resume",
            max_campaigns_per_run=1,
        )
        self.assertEqual(first["status"], "MULTI_CAMPAIGN_PAUSED")
        second_workflow = self.workflow(stub=stub)
        second = second_workflow.resume("pause-resume")
        self.assertEqual(second["status"], "MULTI_CAMPAIGN_COMPLETED")
        self.assertEqual(stub.run_calls, ["critical", "normal"])

    def test_interrupted_running_campaign_is_recovered_with_resume(self) -> None:
        stub = CampaignWorkflowStub()
        workflow = self.workflow(stub=stub)
        portfolio = MultiCampaignPlanner(self.root).plan(
            "Portfolio",
            self.campaigns(),
            portfolio_id="interrupted",
        )
        item = portfolio.campaign("critical")
        item.status = "RUNNING"
        stub.existing["critical"] = {"status": "CAMPAIGN_RUNNING"}
        workflow.store.save(portfolio)
        result = workflow.resume("interrupted", max_campaigns_per_run=1)
        self.assertEqual(result["status"], "MULTI_CAMPAIGN_PAUSED")
        self.assertEqual(stub.resume_calls, ["critical"])

    def test_failure_rolls_back_completed_campaigns_in_reverse(self) -> None:
        stub = CampaignWorkflowStub()
        stub.run_results["normal"] = {
            "success": False,
            "status": "CAMPAIGN_STAGE_FAILED_AND_ROLLED_BACK",
            "errors": ["failure"],
        }
        result = self.workflow(stub=stub).run(
            "Portfolio",
            campaigns=self.campaigns(),
            portfolio_id="rollback-order",
        )
        self.assertEqual(result["status"], "MULTI_CAMPAIGN_FAILED_AND_ROLLED_BACK")
        self.assertEqual(stub.rollback_calls, ["critical"])

    def test_continue_on_failure_runs_independent_campaigns(self) -> None:
        campaigns = self.campaigns()
        campaigns.append(
            {
                "campaign_id": "dependent",
                "objective": "Zależna kampania",
                "priority": "HIGH",
                "depends_on": ["normal"],
                "stages": [
                    self.stage("dependent-1", "app/ai/a.py", "app/autodev/b.py"),
                    self.stage("dependent-2", "app/gui/c.py", "app/core/d.py"),
                ],
            }
        )
        stub = CampaignWorkflowStub()
        stub.run_results["normal"] = {
            "success": False,
            "status": "CAMPAIGN_STAGE_FAILED",
            "errors": ["failure"],
        }
        result = self.workflow(stub=stub).run(
            "Portfolio",
            campaigns=campaigns,
            portfolio_id="continue",
            continue_on_failure=True,
            auto_rollback=False,
            rollback_completed_on_failure=False,
        )
        self.assertEqual(result["status"], "MULTI_CAMPAIGN_PARTIAL_FAILURE")
        self.assertIn("critical", stub.run_calls)
        self.assertEqual(result["portfolio"]["blocked_campaign_ids"], ["dependent"])

    def test_final_validation_failure_rolls_back_all_completed(self) -> None:
        stub = CampaignWorkflowStub()
        result = self.workflow(
            stub=stub,
            validator=ValidatorStub(success=False),
        ).run(
            "Portfolio",
            campaigns=self.campaigns(),
            portfolio_id="final-validation",
        )
        self.assertEqual(
            result["status"],
            "MULTI_CAMPAIGN_FINAL_VALIDATION_FAILED_AND_ROLLED_BACK",
        )
        self.assertEqual(stub.rollback_calls, ["normal", "critical"])

    def test_reprioritize_changes_pending_execution_order(self) -> None:
        workflow = self.workflow()
        workflow.run(
            "Portfolio",
            campaigns=self.campaigns(),
            portfolio_id="reprioritize",
            auto_execute=False,
        )
        result = workflow.reprioritize(
            "reprioritize",
            {"normal": "CRITICAL", "critical": "LOW"},
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["portfolio"]["execution_order"], ["normal", "critical"])

    def test_campaign_internal_pause_pauses_portfolio(self) -> None:
        stub = CampaignWorkflowStub()
        stub.run_results["critical"] = {
            "success": True,
            "status": "CAMPAIGN_PAUSED",
            "errors": [],
        }
        first = self.workflow(stub=stub).run(
            "Portfolio",
            campaigns=self.campaigns(),
            portfolio_id="internal-pause",
        )
        self.assertEqual(first["status"], "MULTI_CAMPAIGN_PAUSED")
        stub.resume_results["critical"] = {
            "success": True,
            "status": "CAMPAIGN_COMPLETED",
            "errors": [],
        }
        second = self.workflow(stub=stub).resume("internal-pause")
        self.assertEqual(second["status"], "MULTI_CAMPAIGN_COMPLETED")

    def test_manual_portfolio_rollback_reverses_completion_order(self) -> None:
        stub = CampaignWorkflowStub()
        workflow = self.workflow(stub=stub)
        completed = workflow.run(
            "Portfolio",
            campaigns=self.campaigns(),
            portfolio_id="manual-rollback",
        )
        self.assertEqual(completed["status"], "MULTI_CAMPAIGN_COMPLETED")
        rolled_back = workflow.rollback("manual-rollback")
        self.assertTrue(rolled_back["success"])
        self.assertEqual(rolled_back["status"], "MULTI_CAMPAIGN_ROLLED_BACK")
        self.assertEqual(stub.rollback_calls, ["normal", "critical"])

    def test_router_reprioritizes_existing_portfolio(self) -> None:
        workflow = self.workflow()
        workflow.run(
            "Portfolio",
            campaigns=self.campaigns(),
            portfolio_id="router-priority",
            auto_execute=False,
        )
        controller = SimpleNamespace(
            project_root=self.root,
            cross_module_workflow=object(),
            multi_campaign_workflow=workflow,
            _normalize=lambda value: str(value).casefold(),
        )
        result = SoftwareEngineerCampaignRouter().try_handle(
            controller,
            command="zmień priorytety portfolio kampanii",
            objective="Portfolio",
            context={
                "operation": "multi_campaign",
                "portfolio_action": "reprioritize",
                "portfolio_id": "router-priority",
                "priorities": {
                    "normal": "CRITICAL",
                    "critical": "LOW",
                },
            },
        )
        self.assertEqual(
            result["portfolio"]["execution_order"],
            ["normal", "critical"],
        )

    def test_campaign_router_routes_portfolio_workflow(self) -> None:
        workflow = self.workflow()
        controller = SimpleNamespace(
            project_root=self.root,
            cross_module_workflow=object(),
            multi_campaign_workflow=workflow,
            _normalize=lambda value: str(value).casefold(),
        )
        result = SoftwareEngineerCampaignRouter().try_handle(
            controller,
            command="uruchom portfolio kampanii",
            objective="Portfolio",
            context={
                "operation": "multi_campaign",
                "portfolio_id": "router-portfolio",
                "portfolio_campaigns": self.campaigns(),
                "auto_execute": False,
            },
        )
        self.assertIsNotNone(result)
        self.assertEqual(result["status"], "MULTI_CAMPAIGN_PLAN_READY")

    def test_formatter_reports_portfolio_progress_and_order(self) -> None:
        result = self.workflow().run(
            "Portfolio",
            campaigns=self.campaigns(),
            portfolio_id="format",
            auto_execute=False,
        )
        text = BrainResponseFormatter()._format_software_engineer_response(result)
        self.assertIn("Portfolio kampanii: format", text)
        self.assertIn("Postęp kampanii: 0/2", text)
        self.assertIn("Kolejność:", text)

    def test_controller_remains_below_audit_limit(self) -> None:
        source = Path(
            AutonomousSoftwareEngineerController.__module__.replace(".", "/") + ".py"
        )
        project_root = Path(__file__).resolve().parents[1]
        controller_path = project_root / source
        self.assertLess(
            len(controller_path.read_text(encoding="utf-8").splitlines()),
            440,
        )


if __name__ == "__main__":
    unittest.main()
