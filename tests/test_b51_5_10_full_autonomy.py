"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations

from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from app.ai.brain_response_formatter import BrainResponseFormatter
from app.ai.software_engineer.autonomous_software_engineer import (
    AutonomousSoftwareEngineerController,
)
from app.ai.software_engineer.full_autonomy_models import FullAutonomyPlan
from app.ai.software_engineer.full_autonomy_planner import FullAutonomyPlanner
from app.ai.software_engineer.full_autonomy_store import FullAutonomyStore
from app.ai.software_engineer.full_autonomy_workflow import FullAutonomyWorkflow
from app.ai.software_engineer.software_engineer_full_autonomy_router import (
    SoftwareEngineerFullAutonomyRouter,
)
from app.ai.software_engineer.software_engineer_command_router import (
    SoftwareEngineerCommandRouter,
)
from app.autodev.execution_result import ExecutionResult


class PortfolioWorkflowStub:

    def __init__(self) -> None:
        self.portfolios: dict[str, dict] = {}
        self.run_calls: list[dict] = []
        self.rollback_calls: list[str] = []

    def run(
        self,
        objective: str,
        *,
        campaigns,
        portfolio_id,
        **kwargs,
    ) -> dict:
        value = {
            "portfolio_id": portfolio_id,
            "objective": objective,
            "status": "MULTI_CAMPAIGN_PLANNED",
            "campaigns": list(campaigns),
            "completed_campaign_ids": [],
            "failed_campaign_ids": [],
            "blocked_campaign_ids": [],
        }
        self.portfolios[portfolio_id] = value
        self.run_calls.append(
            {
                "objective": objective,
                "campaigns": list(campaigns),
                "portfolio_id": portfolio_id,
                **kwargs,
            }
        )
        return {
            "success": True,
            "status": "MULTI_CAMPAIGN_PLANNED",
            "portfolio_id": portfolio_id,
            "portfolio": dict(value),
            "errors": [],
        }

    def rollback(self, portfolio_id: str) -> dict:
        self.rollback_calls.append(portfolio_id)
        return {
            "success": True,
            "status": "MULTI_CAMPAIGN_ROLLED_BACK",
            "portfolio_id": portfolio_id,
            "errors": [],
        }

    def get_portfolio(self, portfolio_id: str):
        value = self.portfolios.get(portfolio_id)
        return dict(value) if value else None


class DirectorStub:

    def __init__(
        self,
        *,
        status: str = "MULTI_CAMPAIGN_COMPLETED",
        success: bool = True,
    ) -> None:
        self.status_value = status
        self.success_value = success
        self.optimize_calls: list[dict] = []
        self.direct_calls: list[dict] = []

    def optimize(
        self,
        portfolio_id: str,
        *,
        constraints,
        apply,
    ) -> dict:
        self.optimize_calls.append(
            {
                "portfolio_id": portfolio_id,
                "constraints": dict(constraints),
                "apply": bool(apply),
            }
        )
        return {
            "success": True,
            "status": "PORTFOLIO_OPTIMIZED",
            "optimization": {
                "average_score": 82.0,
                "selected_campaign_ids": ["autonomy-01-foundation"],
                "deferred_campaigns": [],
                "estimated_minutes": 80,
            },
        }

    def direct(self, portfolio_id: str, **kwargs) -> dict:
        self.direct_calls.append(
            {
                "portfolio_id": portfolio_id,
                **kwargs,
            }
        )
        return {
            "success": self.success_value,
            "status": self.status_value,
            "portfolio_id": portfolio_id,
            "portfolio": {
                "portfolio_id": portfolio_id,
                "campaigns": [{}, {}],
                "completed_campaign_ids": (
                    ["autonomy-01-foundation", "autonomy-02-implementation"]
                    if self.success_value
                    else []
                ),
                "failed_campaign_ids": [],
                "blocked_campaign_ids": [],
            },
            "director_run": {
                "run_id": "director-test",
                "cycles": 2,
                "retries": 1,
            },
            "errors": [] if self.success_value else ["director failure"],
        }


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


class B51510FullAutonomyTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.targets = (
            "app/ai/goal.py",
            "app/autodev/worker.py",
            "app/gui/panel.py",
            "tests/test_goal.py",
            "app/core/state.py",
            "app/memory/history.py",
        )
        for index, relative in enumerate(self.targets):
            target = self.root / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(
                f"VALUE = {index}\n",
                encoding="utf-8",
            )

    def tearDown(self) -> None:
        self.temp.cleanup()

    def planner(self) -> FullAutonomyPlanner:
        return FullAutonomyPlanner(self.root)

    def workflow(
        self,
        *,
        director: DirectorStub | None = None,
        validator: ValidatorStub | None = None,
        portfolio: PortfolioWorkflowStub | None = None,
    ) -> FullAutonomyWorkflow:
        return FullAutonomyWorkflow(
            self.root,
            planner=self.planner(),
            portfolio_workflow=portfolio or PortfolioWorkflowStub(),
            optimizer=MagicMock(),
            director=director or DirectorStub(),
            validator=validator or ValidatorStub(),
        )

    def base_context(self) -> dict:
        return {
            "autonomy_run_id": "autonomy-test",
            "autonomy_targets": list(self.targets),
            "auto_execute": True,
            "auto_approve": False,
            "auto_rollback": True,
            "final_validation": True,
        }

    def test_planner_rejects_empty_large_goal(self) -> None:
        with self.assertRaises(ValueError):
            self.planner().plan(
                "",
                targets=self.targets,
            )

    def test_planner_creates_portfolio_from_one_goal(self) -> None:
        plan = self.planner().plan(
            "Zbuduj bezpieczny system zarządzania celem",
            targets=self.targets,
        )
        self.assertIsInstance(plan, FullAutonomyPlan)
        self.assertGreaterEqual(len(plan.campaigns), 2)
        self.assertEqual(set(plan.target_files), set(self.targets))
        self.assertGreaterEqual(len(plan.subsystems), 2)

    def test_planner_creates_dependency_ordered_campaigns(self) -> None:
        plan = self.planner().plan(
            "Rozwiń autonomiczny przepływ",
            targets=self.targets,
        )
        ids = [item["campaign_id"] for item in plan.campaigns]
        self.assertEqual(plan.execution_order, ids)
        for index, item in enumerate(plan.campaigns[1:], start=1):
            self.assertEqual(item["depends_on"], [ids[index - 1]])

    def test_planner_persists_metrics_and_acceptance_criteria(self) -> None:
        plan = self.planner().plan(
            "Zbuduj pełną autonomię",
            targets=self.targets,
        )
        self.assertGreater(plan.estimated_roi, 0)
        self.assertGreater(plan.estimated_minutes, 0)
        self.assertGreater(plan.confidence, 0)
        self.assertTrue(plan.fingerprint)
        self.assertGreaterEqual(len(plan.acceptance_criteria), 5)

    def test_planner_rejects_path_outside_project(self) -> None:
        outside = self.root.parent / "outside.py"
        outside.write_text("VALUE = 1\n", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.planner().plan(
                "Cel",
                targets=[outside, *self.targets],
            )

    def test_planner_rejects_non_python_target(self) -> None:
        target = self.root / "app/core/value.txt"
        target.write_text("x", encoding="utf-8")
        with self.assertRaises(ValueError):
            self.planner().plan(
                "Cel",
                targets=[target, *self.targets],
            )

    def test_planner_can_use_provided_campaigns(self) -> None:
        stages = [
            {
                "stage_id": "one",
                "objective": "Pierwszy etap",
                "targets": list(self.targets[:3]),
                "allow_same_subsystem": True,
            },
            {
                "stage_id": "two",
                "objective": "Drugi etap",
                "targets": list(self.targets[3:]),
                "allow_same_subsystem": True,
            },
        ]
        campaigns = [
            {
                "campaign_id": "provided-a",
                "objective": "Kampania A",
                "stages": stages,
            },
            {
                "campaign_id": "provided-b",
                "objective": "Kampania B",
                "depends_on": ["provided-a"],
                "stages": stages,
            },
        ]
        plan = self.planner().plan(
            "Cel z dostarczonym planem",
            campaigns=campaigns,
        )
        self.assertEqual(
            [item["campaign_id"] for item in plan.campaigns],
            ["provided-a", "provided-b"],
        )
        self.assertEqual(plan.metadata["planning_source"], "provided_campaigns")

    def test_planner_discovers_targets_from_goal(self) -> None:
        plan = self.planner().plan(
            "Rozbuduj goal worker panel history"
        )
        self.assertGreaterEqual(len(plan.target_files), 4)
        self.assertIn("app/ai/goal.py", plan.target_files)

    def test_store_is_atomic_bounded_and_recent(self) -> None:
        store = FullAutonomyStore(self.root, max_records=10)
        for index in range(12):
            store.save(
                {
                    "run_id": f"run-{index}",
                    "status": "DONE",
                }
            )
        self.assertIsNone(store.get("run-0"))
        self.assertEqual(store.list_recent(limit=1)[0]["run_id"], "run-11")
        self.assertTrue(store.path.is_file())

    def test_plan_only_creates_portfolio_without_execution(self) -> None:
        director = DirectorStub()
        workflow = self.workflow(director=director)
        context = {
            **self.base_context(),
            "auto_execute": False,
            "plan_only": True,
        }
        result = workflow.run(
            "Zaplanuj pełną autonomię",
            context=context,
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "FULL_AUTONOMY_PLAN_READY")
        self.assertFalse(director.direct_calls)
        self.assertTrue(result["plan"]["campaigns"])

    def test_full_workflow_completes_from_one_goal(self) -> None:
        validator = ValidatorStub()
        director = DirectorStub()
        workflow = self.workflow(
            director=director,
            validator=validator,
        )
        result = workflow.run(
            "Wykonaj pełny autonomiczny rozwój",
            context=self.base_context(),
        )
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "FULL_AUTONOMY_COMPLETED")
        self.assertEqual(len(director.direct_calls), 1)
        self.assertEqual(len(validator.calls), 1)
        self.assertTrue(result["final_report"])
        self.assertEqual(result["final_report"]["director_cycles"], 2)

    def test_final_validation_failure_rolls_back_portfolio(self) -> None:
        portfolio = PortfolioWorkflowStub()
        workflow = self.workflow(
            portfolio=portfolio,
            validator=ValidatorStub(success=False),
        )
        result = workflow.run(
            "Cel z końcowym błędem",
            context=self.base_context(),
        )
        self.assertFalse(result["success"])
        self.assertEqual(
            result["status"],
            "FULL_AUTONOMY_FINAL_VALIDATION_FAILED_AND_ROLLED_BACK",
        )
        self.assertEqual(portfolio.rollback_calls, [result["portfolio_id"]])

    def test_director_failure_is_reported(self) -> None:
        workflow = self.workflow(
            director=DirectorStub(
                status="CAMPAIGN_DIRECTOR_STOPPED_FAILURE_LIMIT",
                success=False,
            )
        )
        result = workflow.run(
            "Cel z błędem dyrektora",
            context=self.base_context(),
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "FULL_AUTONOMY_FAILED")
        self.assertIn("director failure", result["errors"])

    def test_director_pause_can_be_resumed(self) -> None:
        director = DirectorStub(
            status="CAMPAIGN_DIRECTOR_PAUSED_CYCLE_LIMIT",
            success=True,
        )
        workflow = self.workflow(director=director)
        first = workflow.run(
            "Cel z pauzą",
            context=self.base_context(),
        )
        self.assertEqual(first["status"], "FULL_AUTONOMY_PAUSED")
        director.status_value = "MULTI_CAMPAIGN_COMPLETED"
        resumed = workflow.resume("autonomy-test")
        self.assertEqual(resumed["status"], "FULL_AUTONOMY_COMPLETED")
        self.assertTrue(resumed["success"])

    def test_completed_run_resume_is_idempotent(self) -> None:
        workflow = self.workflow()
        completed = workflow.run(
            "Cel ukończony",
            context=self.base_context(),
        )
        resumed = workflow.resume(completed["autonomy_run_id"])
        self.assertEqual(resumed["status"], "FULL_AUTONOMY_COMPLETED")
        self.assertEqual(
            resumed["autonomy_run_id"],
            completed["autonomy_run_id"],
        )

    def test_manual_rollback_updates_run(self) -> None:
        portfolio = PortfolioWorkflowStub()
        workflow = self.workflow(portfolio=portfolio)
        completed = workflow.run(
            "Cel do cofnięcia",
            context=self.base_context(),
        )
        result = workflow.rollback(completed["autonomy_run_id"])
        self.assertTrue(result["success"])
        self.assertEqual(result["status"], "FULL_AUTONOMY_ROLLED_BACK")
        self.assertTrue(portfolio.rollback_calls)


    def test_duplicate_run_id_is_rejected_without_overwrite(self) -> None:
        workflow = self.workflow()
        first = workflow.run(
            "Pierwszy cel",
            context=self.base_context(),
        )
        second = workflow.run(
            "Drugi cel",
            context=self.base_context(),
        )
        self.assertTrue(first["success"])
        self.assertFalse(second["success"])
        self.assertEqual(
            second["status"],
            "FULL_AUTONOMY_RUN_ALREADY_EXISTS",
        )
        stored = workflow.store.get("autonomy-test")
        self.assertEqual(stored["objective"], "Pierwszy cel")

    def test_portfolio_planning_failure_stops_execution(self) -> None:
        portfolio = MagicMock()
        portfolio.run.return_value = {
            "success": False,
            "status": "MULTI_CAMPAIGN_PLANNING_FAILED",
            "portfolio": {},
            "errors": ["portfolio failed"],
        }
        director = DirectorStub()
        workflow = FullAutonomyWorkflow(
            self.root,
            planner=self.planner(),
            portfolio_workflow=portfolio,
            optimizer=MagicMock(),
            director=director,
            validator=ValidatorStub(),
        )
        result = workflow.run(
            "Cel z błędem portfolio",
            context=self.base_context(),
        )
        self.assertFalse(result["success"])
        self.assertEqual(
            result["status"],
            "FULL_AUTONOMY_PORTFOLIO_FAILED",
        )
        self.assertFalse(director.direct_calls)

    def test_rollback_exception_is_structured(self) -> None:
        portfolio = PortfolioWorkflowStub()
        workflow = self.workflow(portfolio=portfolio)
        completed = workflow.run(
            "Cel do błędnego cofnięcia",
            context=self.base_context(),
        )
        portfolio.rollback = MagicMock(
            side_effect=PermissionError("locked")
        )
        result = workflow.rollback(
            completed["autonomy_run_id"]
        )
        self.assertFalse(result["success"])
        self.assertEqual(
            result["status"],
            "FULL_AUTONOMY_ROLLBACK_FAILED",
        )
        self.assertIn(
            "PermissionError",
            result["errors"][-1],
        )

    def test_status_and_recent_runs_are_available(self) -> None:
        workflow = self.workflow()
        result = workflow.run(
            "Cel statusu",
            context=self.base_context(),
        )
        status = workflow.status(result["autonomy_run_id"])
        recent = workflow.recent(limit=1)
        self.assertEqual(status["autonomy_run_id"], result["autonomy_run_id"])
        self.assertEqual(recent["status"], "FULL_AUTONOMY_RECENT")
        self.assertEqual(len(recent["autonomy_runs"]), 1)

    def test_unknown_run_is_safe(self) -> None:
        result = self.workflow().status("missing")
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "FULL_AUTONOMY_RUN_NOT_FOUND")

    def test_planning_exception_has_structured_failure(self) -> None:
        planner = MagicMock()
        planner.plan.side_effect = RuntimeError("planner failed")
        workflow = FullAutonomyWorkflow(
            self.root,
            planner=planner,
            portfolio_workflow=PortfolioWorkflowStub(),
            optimizer=MagicMock(),
            director=DirectorStub(),
            validator=ValidatorStub(),
        )
        result = workflow.run(
            "Cel",
            context={
                "autonomy_run_id": "failure",
            },
        )
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "FULL_AUTONOMY_PLANNING_FAILED")
        self.assertIn("planner failed", result["errors"][0])

    def test_router_detects_and_runs_full_autonomy(self) -> None:
        workflow = MagicMock()
        workflow.run.return_value = {
            "success": True,
            "status": "FULL_AUTONOMY_COMPLETED",
            "operation": "full_autonomy",
        }
        controller = SimpleNamespace(
            project_root=self.root,
            full_autonomy_workflow=workflow,
            _normalize=lambda value: str(value).casefold(),
        )
        result = SoftwareEngineerFullAutonomyRouter().try_handle(
            controller,
            command="uruchom pełną autonomię dla dużego celu",
            objective="Duży cel",
            context={"operation": "full_autonomy"},
        )
        self.assertEqual(result["status"], "FULL_AUTONOMY_COMPLETED")
        workflow.run.assert_called_once()

    def test_router_routes_status_resume_recent_and_rollback(self) -> None:
        workflow = MagicMock()
        workflow.status.return_value = {"status": "STATUS"}
        workflow.resume.return_value = {"status": "RESUME"}
        workflow.recent.return_value = {"status": "RECENT"}
        workflow.rollback.return_value = {"status": "ROLLBACK"}
        controller = SimpleNamespace(
            project_root=self.root,
            full_autonomy_workflow=workflow,
            _normalize=lambda value: str(value).casefold(),
        )
        router = SoftwareEngineerFullAutonomyRouter()
        values = {}
        for action in ("status", "resume", "recent", "rollback"):
            result = router.try_handle(
                controller,
                command="pełna autonomia",
                objective="Cel",
                context={
                    "operation": "full_autonomy",
                    "full_autonomy_action": action,
                    "autonomy_run_id": "run-1",
                },
            )
            values[action] = result["status"]
        self.assertEqual(
            values,
            {
                "status": "STATUS",
                "resume": "RESUME",
                "recent": "RECENT",
                "rollback": "ROLLBACK",
            },
        )

    def test_router_requires_run_id_for_state_actions(self) -> None:
        controller = SimpleNamespace(
            project_root=self.root,
            full_autonomy_workflow=MagicMock(),
            _normalize=lambda value: str(value).casefold(),
        )
        result = SoftwareEngineerFullAutonomyRouter().try_handle(
            controller,
            command="status pełnej autonomii",
            objective="Cel",
            context={
                "operation": "full_autonomy",
                "full_autonomy_action": "status",
            },
        )
        self.assertEqual(result["status"], "FULL_AUTONOMY_RUN_ID_REQUIRED")

    def test_command_router_accepts_context_only_full_autonomy(
        self,
    ) -> None:
        workflow = MagicMock()
        workflow.run.return_value = {
            "success": True,
            "status": "FULL_AUTONOMY_PLAN_READY",
            "operation": "full_autonomy",
        }
        controller = SimpleNamespace(
            project_root=self.root,
            full_autonomy_workflow=workflow,
            can_handle=lambda command: False,
            _normalize=lambda value: str(value).casefold(),
            _extract_objective=lambda command: str(command),
        )

        result = SoftwareEngineerCommandRouter().handle(
            controller,
            "wykonaj cel",
            {
                "operation": "full_autonomy",
                "objective": "Duży cel",
                "auto_execute": False,
            },
        )

        self.assertEqual(
            result["status"],
            "FULL_AUTONOMY_PLAN_READY",
        )
        workflow.run.assert_called_once()

    def test_polish_accusative_plan_command_routes_to_full_autonomy(
        self,
    ) -> None:
        workflow = MagicMock()
        workflow.run.return_value = {
            "success": True,
            "status": "FULL_AUTONOMY_PLAN_READY",
            "operation": "full_autonomy",
            "autonomy_run_id": "autonomy-polish-command",
            "errors": [],
        }
        controller = SimpleNamespace(
            project_root=self.root,
            full_autonomy_workflow=workflow,
            can_handle=(
                AutonomousSoftwareEngineerController.can_handle
            ),
            _normalize=(
                AutonomousSoftwareEngineerController._normalize
            ),
            _extract_objective=lambda command: str(command),
        )
        command = (
            "Zaplanuj pełną autonomię dla dużego celu: "
            "utwórz bezpieczny moduł demonstracyjny"
        )

        result = SoftwareEngineerCommandRouter().handle(
            controller,
            command,
            {
                "auto_execute": True,
                "auto_approve": True,
                "auto_rollback": True,
                "metadata": {
                    "source": "Brain",
                },
            },
        )

        self.assertEqual(
            result["status"],
            "FULL_AUTONOMY_PLAN_READY",
        )
        workflow.run.assert_called_once()
        call_context = workflow.run.call_args.kwargs[
            "context"
        ]
        self.assertTrue(
            call_context["plan_only"]
        )
        self.assertFalse(
            call_context["auto_execute"]
        )

    def test_full_autonomy_router_accepts_polish_grammar_variants(
        self,
    ) -> None:
        router = SoftwareEngineerFullAutonomyRouter()
        controller = SimpleNamespace(
            _normalize=(
                AutonomousSoftwareEngineerController._normalize
            ),
        )

        for command in (
            "Zaplanuj pełną autonomię dla dużego celu",
            "Pokaż status pełnej autonomii",
            "Uruchom pelna autonomie dla duzego celu",
        ):
            with self.subTest(command=command):
                self.assertTrue(
                    router._is_full_autonomy(
                        controller,
                        command=command,
                        context={},
                    )
                )

    def test_controller_detects_full_autonomy_commands(self) -> None:
        self.assertTrue(
            AutonomousSoftwareEngineerController.can_handle(
                "uruchom pełną autonomię dla dużego celu"
            )
        )
        self.assertTrue(
            AutonomousSoftwareEngineerController.can_handle(
                "full autonomy for one large goal"
            )
        )

    def test_brain_formatter_reports_full_autonomy(self) -> None:
        text = BrainResponseFormatter()._format_software_engineer_response(
            {
                "success": True,
                "status": "FULL_AUTONOMY_COMPLETED",
                "operation": "full_autonomy",
                "autonomy_run_id": "autonomy-1",
                "autonomy_run": {
                    "objective": "Duży cel",
                },
                "plan": {
                    "campaigns": [{}, {}],
                    "target_files": ["a.py", "b.py", "c.py", "d.py"],
                },
                "director_run": {
                    "cycles": 2,
                    "retries": 1,
                },
                "final_validation": {
                    "success": True,
                },
                "report_path": "data/autodev/full_autonomy_runs.json",
            }
        )
        self.assertIn("Pełna autonomia: FULL_AUTONOMY_COMPLETED", text)
        self.assertIn("Kampanie: 2", text)
        self.assertIn("Walidacja końcowa: OK", text)

    def test_controller_remains_below_audit_limit(self) -> None:
        module_path = Path(
            AutonomousSoftwareEngineerController.__module__.replace(".", "/")
            + ".py"
        )
        controller_path = Path(__file__).resolve().parents[1] / module_path
        self.assertLess(
            len(controller_path.read_text(encoding="utf-8").splitlines()),
            440,
        )


if __name__ == "__main__":
    unittest.main()
