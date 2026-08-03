"""Moduł JARVIS OS utrzymywany przez bezpieczny AutoDev."""

from __future__ import annotations

from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock

from app.ai.software_engineer.autonomous_campaign_director import (
    AutonomousCampaignDirector,
)
from app.ai.software_engineer.autonomous_software_engineer import (
    AutonomousSoftwareEngineerController,
)
from app.ai.software_engineer.change_campaign_workflow import (
    ChangeCampaignWorkflow,
)
from app.ai.software_engineer.full_autonomy_execution_tracker import (
    FullAutonomyExecutionTracker,
)
from app.ai.software_engineer.full_autonomy_feature_intent import (
    FullAutonomyFeatureIntent,
)
from app.ai.software_engineer.full_autonomy_planner import (
    FullAutonomyPlanner,
)
from app.ai.software_engineer.full_autonomy_workflow import (
    FullAutonomyWorkflow,
)
from app.ai.software_engineer.software_engineer_full_autonomy_formatter import (
    format_full_autonomy_response,
)
from app.ai.software_engineer.software_engineer_full_autonomy_router import (
    SoftwareEngineerFullAutonomyRouter,
)
from app.autodev.execution_result import ExecutionResult


DEMO_OBJECTIVE = (
    "Utwórz bezpieczny demonstracyjny moduł "
    "app\\autonomy_demo składający się z modelu, "
    "repozytorium, serwisu, kontrolera oraz testów, "
    "bez modyfikowania istniejących modułów projektu"
)


class ValidatorStub:

    def __init__(
        self,
        success: bool = True,
    ) -> None:
        self.success = success
        self.calls: list[dict] = []

    def run_test_suite(
        self,
        *,
        changed_files,
        full_suite,
    ) -> ExecutionResult:
        self.calls.append(
            {
                "changed_files": list(
                    changed_files
                ),
                "full_suite": bool(
                    full_suite
                ),
            }
        )
        return ExecutionResult(
            success=self.success,
            step_name="run_test_suite",
            message=(
                "OK"
                if self.success
                else "FAIL"
            ),
            errors=(
                []
                if self.success
                else ["validation failed"]
            ),
        )


class FeatureWorkflowStub:

    def __init__(
        self,
        *,
        status: str = "COMPLETED",
        success: bool = True,
    ) -> None:
        self.status = status
        self.success = success
        self.calls: list[dict] = []

    def run(
        self,
        objective: str,
        **kwargs,
    ) -> dict:
        self.calls.append(
            {
                "objective": objective,
                **kwargs,
            }
        )
        return {
            "success": self.success,
            "status": self.status,
            "changed_files": list(
                dict(
                    kwargs.get(
                        "replacements",
                        {},
                    )
                )
            ),
            "errors": (
                []
                if self.success
                else ["feature failed"]
            ),
        }


class CrossWorkflowGuard:

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def run(
        self,
        objective: str,
        **kwargs,
    ) -> dict:
        self.calls.append(
            {
                "objective": objective,
                **kwargs,
            }
        )
        return {
            "success": False,
            "status": "UNEXPECTED_CROSS_MODULE_CALL",
            "errors": [
                "Cross-module workflow should not run.",
            ],
        }


class PortfolioWorkflowStub:

    def __init__(self) -> None:
        self.portfolios: dict[str, dict] = {}
        self.run_calls: list[dict] = []
        self.rollback_calls: list[str] = []
        self.pause_calls: list[str] = []

    def run(
        self,
        objective: str,
        *,
        campaigns,
        portfolio_id,
        **kwargs,
    ) -> dict:
        campaign_values = [
            {
                **dict(item),
                "status": "PENDING",
                "result": {},
            }
            for item in campaigns
        ]
        value = {
            "portfolio_id": portfolio_id,
            "objective": objective,
            "status": "MULTI_CAMPAIGN_PLAN_READY",
            "campaigns": campaign_values,
            "completed_campaign_ids": [],
            "failed_campaign_ids": [],
            "blocked_campaign_ids": [],
            "current_campaign_id": "",
        }
        self.portfolios[
            portfolio_id
        ] = value
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
            "status": value["status"],
            "portfolio_id": portfolio_id,
            "portfolio": dict(value),
            "errors": [],
        }

    def get_portfolio(
        self,
        portfolio_id: str,
    ) -> dict | None:
        value = self.portfolios.get(
            portfolio_id
        )
        return (
            dict(value)
            if value is not None
            else None
        )

    def pause(
        self,
        portfolio_id: str,
    ) -> dict:
        self.pause_calls.append(
            portfolio_id
        )
        value = self.portfolios[
            portfolio_id
        ]
        value["status"] = "MULTI_CAMPAIGN_PAUSED"
        return {
            "success": True,
            "status": value["status"],
            "portfolio_id": portfolio_id,
            "portfolio": dict(value),
            "errors": [],
        }

    def rollback(
        self,
        portfolio_id: str,
    ) -> dict:
        self.rollback_calls.append(
            portfolio_id
        )
        return {
            "success": True,
            "status": "MULTI_CAMPAIGN_ROLLED_BACK",
            "portfolio_id": portfolio_id,
            "errors": [],
        }


class CallbackDirectorStub:

    def __init__(self) -> None:
        self.calls: list[dict] = []

    def optimize(
        self,
        portfolio_id: str,
        *,
        constraints,
        apply,
    ) -> dict:
        return {
            "success": True,
            "status": "PORTFOLIO_OPTIMIZED",
            "optimization": {
                "average_score": 88.0,
                "selected_campaign_ids": [
                    "autonomy-01-feature-foundation",
                ],
                "deferred_campaigns": [],
            },
        }

    def direct(
        self,
        portfolio_id: str,
        **kwargs,
    ) -> dict:
        self.calls.append(
            {
                "portfolio_id": portfolio_id,
                **kwargs,
            }
        )
        callback = kwargs.get(
            "progress_callback"
        )
        portfolio = {
            "portfolio_id": portfolio_id,
            "status": "MULTI_CAMPAIGN_RUNNING",
            "current_campaign_id": (
                "autonomy-01-feature-foundation"
            ),
            "campaigns": [
                {
                    "campaign_id": (
                        "autonomy-01-feature-foundation"
                    ),
                    "status": "RUNNING",
                    "stages": [
                        {
                            "stage_id": "create",
                            "status": "COMPLETED",
                        },
                        {
                            "stage_id": "verify",
                            "status": "RUNNING",
                        },
                    ],
                    "result": {
                        "changed_files": [
                            "app/autonomy_demo/models.py",
                        ],
                    },
                },
                {
                    "campaign_id": (
                        "autonomy-02-feature-delivery"
                    ),
                    "status": "PENDING",
                    "stages": [],
                    "result": {},
                },
            ],
            "completed_campaign_ids": [],
            "failed_campaign_ids": [],
            "blocked_campaign_ids": [],
        }
        if callable(callback):
            callback(
                "DIRECTOR_CYCLE_OPTIMIZED",
                {
                    "portfolio": portfolio,
                    "director_run": {
                        "run_id": "director-b516",
                        "cycles": 1,
                        "retries": 0,
                    },
                    "metadata": {
                        "cycle": 1,
                    },
                },
            )
        completed = {
            **portfolio,
            "status": "MULTI_CAMPAIGN_COMPLETED",
            "current_campaign_id": "",
            "completed_campaign_ids": [
                "autonomy-01-feature-foundation",
                "autonomy-02-feature-delivery",
            ],
            "campaigns": [
                {
                    **item,
                    "status": "COMPLETED",
                }
                for item in portfolio["campaigns"]
            ],
        }
        return {
            "success": True,
            "status": "MULTI_CAMPAIGN_COMPLETED",
            "portfolio_id": portfolio_id,
            "portfolio": completed,
            "director_run": {
                "run_id": "director-b516",
                "cycles": 2,
                "retries": 0,
            },
            "errors": [],
        }


class B516FullAutonomyExecutionEngineTests(
    unittest.TestCase
):

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(
            self.temp.name
        )
        (
            self.root
            / "app"
        ).mkdir()
        (
            self.root
            / "tests"
        ).mkdir()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_feature_intent_detects_new_module(
        self,
    ) -> None:
        intent = FullAutonomyFeatureIntent(
            self.root
        ).detect(
            DEMO_OBJECTIVE
        )

        self.assertIsNotNone(intent)
        self.assertEqual(
            intent["package_path"],
            "app/autonomy_demo",
        )
        self.assertEqual(
            intent["feature_name"],
            "AutonomyDemo",
        )
        self.assertEqual(
            len(intent["target_files"]),
            6,
        )
        self.assertIn(
            "app/autonomy_demo/repository.py",
            intent["replacements"],
        )

    def test_feature_intent_does_not_write_during_plan(
        self,
    ) -> None:
        intent = FullAutonomyFeatureIntent(
            self.root
        ).detect(
            DEMO_OBJECTIVE
        )

        self.assertIsNotNone(intent)
        self.assertFalse(
            (
                self.root
                / "app/autonomy_demo"
            ).exists()
        )

    def test_feature_intent_rejects_existing_module(
        self,
    ) -> None:
        target = (
            self.root
            / "app/autonomy_demo/models.py"
        )
        target.parent.mkdir(
            parents=True
        )
        target.write_text(
            "VALUE = 1\n",
            encoding="utf-8",
        )

        with self.assertRaises(
            ValueError
        ):
            FullAutonomyFeatureIntent(
                self.root
            ).detect(
                DEMO_OBJECTIVE
            )

    def test_feature_intent_requires_creation_language(
        self,
    ) -> None:
        result = FullAutonomyFeatureIntent(
            self.root
        ).detect(
            "Sprawdź dokumentację app\\autonomy_demo"
        )

        self.assertIsNone(result)

    def test_planner_builds_executable_feature_campaigns(
        self,
    ) -> None:
        plan = FullAutonomyPlanner(
            self.root
        ).plan(
            DEMO_OBJECTIVE
        )

        self.assertEqual(
            plan.metadata["planning_source"],
            "new_feature_intent",
        )
        self.assertEqual(
            len(plan.campaigns),
            2,
        )
        kinds = [
            stage["metadata"][
                "execution_kind"
            ]
            for campaign in plan.campaigns
            for stage in campaign["stages"]
        ]
        self.assertIn(
            "feature_creation",
            kinds,
        )
        self.assertIn(
            "validation_only",
            kinds,
        )

    def test_planner_feature_targets_may_be_new(
        self,
    ) -> None:
        plan = FullAutonomyPlanner(
            self.root
        ).plan(
            DEMO_OBJECTIVE
        )

        self.assertTrue(
            all(
                not (
                    self.root
                    / path
                ).exists()
                for path in plan.target_files
            )
        )

    def test_campaign_routes_feature_creation_stage(
        self,
    ) -> None:
        intent = FullAutonomyFeatureIntent(
            self.root
        ).detect(
            DEMO_OBJECTIVE
        )
        feature = FeatureWorkflowStub()
        cross = CrossWorkflowGuard()
        validator = ValidatorStub()
        workflow = ChangeCampaignWorkflow(
            self.root,
            feature_workflow=feature,
            cross_module_workflow=cross,
            validator=validator,
        )
        result = workflow.run(
            DEMO_OBJECTIVE,
            stages=intent["campaigns"][0][
                "stages"
            ],
            campaign_id="feature-campaign",
            auto_execute=True,
            auto_approve=True,
            auto_rollback=True,
            final_validation=True,
        )

        self.assertTrue(
            result["success"]
        )
        self.assertEqual(
            result["status"],
            "CAMPAIGN_COMPLETED",
        )
        self.assertEqual(
            len(feature.calls),
            1,
        )
        self.assertFalse(
            cross.calls
        )

    def test_validation_only_stage_uses_validator(
        self,
    ) -> None:
        intent = FullAutonomyFeatureIntent(
            self.root
        ).detect(
            DEMO_OBJECTIVE
        )
        validator = ValidatorStub()
        workflow = ChangeCampaignWorkflow(
            self.root,
            feature_workflow=FeatureWorkflowStub(),
            cross_module_workflow=CrossWorkflowGuard(),
            validator=validator,
        )
        result = workflow.run(
            DEMO_OBJECTIVE,
            stages=intent["campaigns"][1][
                "stages"
            ],
            campaign_id="validation-campaign",
            auto_execute=True,
            auto_approve=True,
            auto_rollback=True,
            final_validation=False,
        )

        self.assertTrue(
            result["success"]
        )
        self.assertEqual(
            len(validator.calls),
            2,
        )
        self.assertTrue(
            validator.calls[-1][
                "full_suite"
            ]
        )

    def test_feature_failure_rolls_back_campaign(
        self,
    ) -> None:
        intent = FullAutonomyFeatureIntent(
            self.root
        ).detect(
            DEMO_OBJECTIVE
        )
        workflow = ChangeCampaignWorkflow(
            self.root,
            feature_workflow=FeatureWorkflowStub(
                success=False,
                status="FEATURE_EXECUTION_FAILED",
            ),
            cross_module_workflow=CrossWorkflowGuard(),
            validator=ValidatorStub(),
        )
        result = workflow.run(
            DEMO_OBJECTIVE,
            stages=intent["campaigns"][0][
                "stages"
            ],
            campaign_id="failed-feature-campaign",
            auto_execute=True,
            auto_approve=True,
            auto_rollback=True,
            final_validation=True,
        )

        self.assertFalse(
            result["success"]
        )
        self.assertIn(
            "ROLLED_BACK",
            result["status"],
        )

    def test_tracker_reports_campaign_and_stage_progress(
        self,
    ) -> None:
        portfolio = PortfolioWorkflowStub()
        portfolio.portfolios["portfolio-1"] = {
            "portfolio_id": "portfolio-1",
            "status": "MULTI_CAMPAIGN_RUNNING",
            "current_campaign_id": "campaign-a",
            "campaigns": [
                {
                    "campaign_id": "campaign-a",
                    "status": "RUNNING",
                    "stages": [
                        {
                            "stage_id": "one",
                            "status": "COMPLETED",
                        },
                        {
                            "stage_id": "two",
                            "status": "RUNNING",
                        },
                    ],
                    "result": {
                        "changed_files": [
                            "app/demo/a.py",
                        ],
                    },
                },
                {
                    "campaign_id": "campaign-b",
                    "status": "PENDING",
                    "stages": [
                        {
                            "stage_id": "three",
                            "status": "PENDING",
                        },
                    ],
                    "result": {},
                },
            ],
        }
        tracker = FullAutonomyExecutionTracker(
            self.root,
            portfolio_workflow=portfolio,
        )
        run = {
            "status": "FULL_AUTONOMY_RUNNING",
            "portfolio_id": "portfolio-1",
            "execution": {},
            "plan": {
                "target_files": [
                    "app/demo/a.py",
                ],
            },
        }
        snapshot = tracker.snapshot(
            run,
            event="TEST",
        )

        self.assertEqual(
            snapshot["campaigns_total"],
            2,
        )
        self.assertEqual(
            snapshot["stages_completed"],
            1,
        )
        self.assertEqual(
            snapshot["progress_percent"],
            33.33,
        )
        self.assertEqual(
            snapshot["current_campaign_id"],
            "campaign-a",
        )

    def test_tracker_does_not_mark_planned_files_as_changed(
        self,
    ) -> None:
        portfolio = PortfolioWorkflowStub()
        portfolio.portfolios["portfolio-plan"] = {
            "portfolio_id": "portfolio-plan",
            "status": "MULTI_CAMPAIGN_PLAN_READY",
            "campaigns": [],
            "current_campaign_id": "",
        }
        tracker = FullAutonomyExecutionTracker(
            self.root,
            portfolio_workflow=portfolio,
        )
        snapshot = tracker.snapshot(
            {
                "status": "FULL_AUTONOMY_PLAN_READY",
                "portfolio_id": "portfolio-plan",
                "plan": {
                    "target_files": [
                        "app/demo/new.py",
                    ],
                },
                "execution": {},
            },
            event="PLAN",
        )

        self.assertEqual(
            snapshot["changed_files"],
            [],
        )

    def test_tracker_rejects_paths_outside_project(
        self,
    ) -> None:
        portfolio = PortfolioWorkflowStub()
        portfolio.portfolios["portfolio-safe"] = {
            "portfolio_id": "portfolio-safe",
            "status": "MULTI_CAMPAIGN_RUNNING",
            "current_campaign_id": "",
            "campaigns": [
                {
                    "campaign_id": "safe",
                    "status": "RUNNING",
                    "result": {
                        "changed_files": [
                            "../outside.py",
                            "app/safe.py",
                        ],
                    },
                },
            ],
        }
        tracker = FullAutonomyExecutionTracker(
            self.root,
            portfolio_workflow=portfolio,
        )
        snapshot = tracker.snapshot(
            {
                "status": "FULL_AUTONOMY_RUNNING",
                "portfolio_id": "portfolio-safe",
                "execution": {},
                "plan": {},
            },
            event="SAFE",
        )

        self.assertEqual(
            snapshot["changed_files"],
            ["app/safe.py"],
        )

    def workflow(
        self,
    ) -> FullAutonomyWorkflow:
        portfolio = PortfolioWorkflowStub()
        return FullAutonomyWorkflow(
            self.root,
            planner=FullAutonomyPlanner(
                self.root
            ),
            portfolio_workflow=portfolio,
            optimizer=MagicMock(),
            director=CallbackDirectorStub(),
            validator=ValidatorStub(),
        )

    def test_plan_only_persists_execution_state(
        self,
    ) -> None:
        result = self.workflow().run(
            DEMO_OBJECTIVE,
            context={
                "autonomy_run_id": "plan-b516",
                "auto_execute": False,
                "plan_only": True,
            },
        )

        self.assertEqual(
            result["status"],
            "FULL_AUTONOMY_PLAN_READY",
        )
        self.assertEqual(
            result["execution"]["status"],
            "PLAN_READY",
        )
        self.assertEqual(
            result["execution"]["changed_files"],
            [],
        )

    def test_execute_runs_existing_plan(
        self,
    ) -> None:
        workflow = self.workflow()
        planned = workflow.run(
            DEMO_OBJECTIVE,
            context={
                "autonomy_run_id": "execute-b516",
                "auto_execute": False,
                "plan_only": True,
            },
        )
        result = workflow.execute(
            planned["autonomy_run_id"],
            context={
                "auto_approve": True,
            },
        )

        self.assertTrue(
            result["success"]
        )
        self.assertEqual(
            result["status"],
            "FULL_AUTONOMY_COMPLETED",
        )
        self.assertEqual(
            result["execution"]["progress_percent"],
            100.0,
        )
        self.assertTrue(
            result["execution"]["checkpoints"],
        )

    def test_execute_unknown_run_is_safe(
        self,
    ) -> None:
        result = self.workflow().execute(
            "missing"
        )

        self.assertEqual(
            result["status"],
            "FULL_AUTONOMY_RUN_NOT_FOUND",
        )

    def test_pause_updates_run_and_portfolio(
        self,
    ) -> None:
        workflow = self.workflow()
        planned = workflow.run(
            DEMO_OBJECTIVE,
            context={
                "autonomy_run_id": "pause-b516",
                "auto_execute": False,
                "plan_only": True,
            },
        )
        result = workflow.pause(
            planned["autonomy_run_id"]
        )

        self.assertTrue(
            result["success"]
        )
        self.assertEqual(
            result["status"],
            "FULL_AUTONOMY_PAUSED",
        )
        self.assertEqual(
            result["execution"]["status"],
            "PAUSED",
        )

    def test_status_refreshes_execution_snapshot(
        self,
    ) -> None:
        workflow = self.workflow()
        planned = workflow.run(
            DEMO_OBJECTIVE,
            context={
                "autonomy_run_id": "status-b516",
                "auto_execute": False,
                "plan_only": True,
            },
        )
        result = workflow.status(
            planned["autonomy_run_id"]
        )

        self.assertIn(
            "execution",
            result,
        )
        self.assertTrue(
            result["execution"]["updated_at"],
        )

    def test_router_executes_planned_run(
        self,
    ) -> None:
        workflow = MagicMock()
        workflow.execute.return_value = {
            "status": "FULL_AUTONOMY_COMPLETED",
        }
        controller = SimpleNamespace(
            project_root=self.root,
            full_autonomy_workflow=workflow,
            _normalize=(
                AutonomousSoftwareEngineerController._normalize
            ),
        )
        result = SoftwareEngineerFullAutonomyRouter().try_handle(
            controller,
            command=(
                "Wykonaj zaplanowaną pełną autonomię"
            ),
            objective="Cel",
            context={
                "operation": "full_autonomy",
                "autonomy_run_id": "run-b516",
            },
        )

        self.assertEqual(
            result["status"],
            "FULL_AUTONOMY_COMPLETED",
        )
        workflow.execute.assert_called_once()

    def test_router_extracts_run_id_from_execute_command(
        self,
    ) -> None:
        workflow = MagicMock()
        workflow.execute.return_value = {
            "status": "FULL_AUTONOMY_COMPLETED",
        }
        controller = SimpleNamespace(
            project_root=self.root,
            full_autonomy_workflow=workflow,
            _normalize=(
                AutonomousSoftwareEngineerController._normalize
            ),
        )

        result = SoftwareEngineerFullAutonomyRouter().try_handle(
            controller,
            command=(
                "Wykonaj zaplanowaną pełną autonomię "
                "autonomy-099e35b296d343db8b52d304d869848c"
            ),
            objective="Cel",
            context={},
        )

        self.assertEqual(
            result["status"],
            "FULL_AUTONOMY_COMPLETED",
        )
        workflow.execute.assert_called_once_with(
            "autonomy-099e35b296d343db8b52d304d869848c",
            context={},
        )

    def test_context_run_id_has_priority_over_command_id(
        self,
    ) -> None:
        value = SoftwareEngineerFullAutonomyRouter._run_id(
            command="Status pełnej autonomii autonomy-from-command",
            context={
                "autonomy_run_id": "autonomy-from-context",
            },
        )

        self.assertEqual(
            value,
            "autonomy-from-context",
        )

    def test_router_pauses_run(
        self,
    ) -> None:
        workflow = MagicMock()
        workflow.pause.return_value = {
            "status": "FULL_AUTONOMY_PAUSED",
        }
        controller = SimpleNamespace(
            project_root=self.root,
            full_autonomy_workflow=workflow,
            _normalize=(
                AutonomousSoftwareEngineerController._normalize
            ),
        )
        result = SoftwareEngineerFullAutonomyRouter().try_handle(
            controller,
            command="Wstrzymaj pełną autonomię",
            objective="Cel",
            context={
                "autonomy_run_id": "run-b516",
            },
        )

        self.assertEqual(
            result["status"],
            "FULL_AUTONOMY_PAUSED",
        )
        workflow.pause.assert_called_once_with(
            "run-b516"
        )

    def test_formatter_reports_live_progress(
        self,
    ) -> None:
        text = format_full_autonomy_response(
            {
                "status": "FULL_AUTONOMY_RUNNING",
                "autonomy_run_id": "run-b516",
                "execution": {
                    "progress_percent": 50.0,
                    "campaigns_completed": 1,
                    "campaigns_total": 2,
                    "stages_completed": 2,
                    "stages_total": 4,
                    "current_campaign_id": "campaign-2",
                    "current_stage_id": "stage-3",
                    "changed_files": [
                        "app/demo.py",
                    ],
                },
            }
        )

        self.assertIn(
            "Postęp: 50.0%",
            text,
        )
        self.assertIn(
            "Bieżąca kampania: campaign-2",
            text,
        )
        self.assertIn(
            "Zmienione pliki: 1",
            text,
        )

    def test_director_notify_is_exception_safe(
        self,
    ) -> None:
        callback = MagicMock(
            side_effect=RuntimeError("ui closed")
        )

        AutonomousCampaignDirector._notify(
            callback,
            "TEST_EVENT",
            run={
                "run_id": "director-test",
            },
            portfolio={},
        )

        callback.assert_called_once()

    def test_controller_stays_below_audit_limit(
        self,
    ) -> None:
        module_path = Path(
            AutonomousSoftwareEngineerController
            .__module__
            .replace(
                ".",
                "/",
            )
            + ".py"
        )
        path = (
            Path(__file__).resolve().parents[1]
            / module_path
        )

        self.assertLess(
            len(
                path.read_text(
                    encoding="utf-8"
                ).splitlines()
            ),
            440,
        )


if __name__ == "__main__":
    unittest.main()
