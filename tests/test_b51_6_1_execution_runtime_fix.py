from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from app.ai.software_engineer.autonomous_campaign_director import (
    AutonomousCampaignDirector,
)
from app.ai.software_engineer.full_autonomy_execution_tracker import (
    FullAutonomyExecutionTracker,
)
from app.ai.software_engineer.full_autonomy_planner import (
    FullAutonomyPlanner,
)
from app.ai.software_engineer.full_autonomy_workflow import (
    FullAutonomyWorkflow,
)
from app.autodev.developer_controller import DeveloperController
from app.autodev.developer_request import DeveloperRequest


OBJECTIVE = (
    "Utwórz bezpieczny demonstracyjny moduł "
    "app\\autonomy_demo składający się z modelu, "
    "repozytorium, serwisu, kontrolera oraz testów, "
    "bez modyfikowania istniejących modułów projektu"
)


class PortfolioTrackerStub:

    def __init__(self, root: Path, portfolio: dict) -> None:
        self.root = root
        self.portfolio = portfolio

    def get_portfolio(self, portfolio_id: str) -> dict:
        return dict(self.portfolio)


class B5161ExecutionRuntimeFixTests(unittest.TestCase):

    def test_isolated_controller_skips_missing_test_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            app = root / "app"
            gui = app / "gui"
            gui.mkdir(parents=True)
            (app / "__init__.py").write_text("", encoding="utf-8")
            (gui / "__init__.py").write_text("", encoding="utf-8")
            (gui / "main_window.py").write_text(
                "class MainWindow:\n    pass\n",
                encoding="utf-8",
            )
            target = app / "sample.py"
            target.write_text("VALUE = 1\n", encoding="utf-8")
            controller = DeveloperController(project_root=root)

            self.assertFalse(controller.executor.run_tests)

            result = controller.prepare(
                DeveloperRequest(
                    goal="Zmień wartość.",
                    target="app.sample",
                    mode="file",
                    path=str(target),
                    proposed_content="VALUE = 2\n",
                )
            )
            self.assertTrue(result.success)
            final = controller.approve_and_execute()
            self.assertTrue(final.success)
            self.assertEqual(target.read_text(encoding="utf-8"), "VALUE = 2\n")

    def test_planner_campaign_ids_are_unique_per_portfolio(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "app").mkdir()
            (root / "tests").mkdir()
            planner = FullAutonomyPlanner(root)
            first = planner.plan(OBJECTIVE, portfolio_id="portfolio-one")
            second = planner.plan(OBJECTIVE, portfolio_id="portfolio-two")
            first_ids = {item["campaign_id"] for item in first.campaigns}
            second_ids = {item["campaign_id"] for item in second.campaigns}

            self.assertTrue(first_ids.isdisjoint(second_ids))
            self.assertTrue(all(value.startswith("fa-") for value in first_ids))
            self.assertEqual(first.execution_order, [item["campaign_id"] for item in first.campaigns])

    def test_tracker_normalizes_duplicate_absolute_and_relative_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            path = root / "app/demo.py"
            path.parent.mkdir(parents=True)
            path.write_text("VALUE = 1\n", encoding="utf-8")
            portfolio = {
                "portfolio_id": "p",
                "status": "MULTI_CAMPAIGN_RUNNING",
                "current_campaign_id": "",
                "campaigns": [{
                    "campaign_id": "c",
                    "status": "COMPLETED",
                    "result": {"changed_files": ["app/demo.py", str(path)]},
                    "stages": [],
                }],
            }
            tracker = FullAutonomyExecutionTracker(
                root,
                portfolio_workflow=PortfolioTrackerStub(root, portfolio),
            )
            snapshot = tracker.snapshot({
                "status": "FULL_AUTONOMY_RUNNING",
                "portfolio_id": "p",
                "plan": {"target_files": ["app/demo.py"]},
                "execution": {},
            })
            self.assertEqual(snapshot["changed_files"], ["app/demo.py"])

    def test_tracker_excludes_rolled_back_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            portfolio = {
                "portfolio_id": "p",
                "status": "MULTI_CAMPAIGN_PAUSED",
                "current_campaign_id": "",
                "campaigns": [{
                    "campaign_id": "c",
                    "status": "FAILED",
                    "result": {"changed_files": ["app/demo.py"]},
                    "stages": [{
                        "stage_id": "create",
                        "status": "ROLLED_BACK",
                        "result": {"changed_files": ["app/demo.py"]},
                    }],
                }],
            }
            tracker = FullAutonomyExecutionTracker(
                root,
                portfolio_workflow=PortfolioTrackerStub(root, portfolio),
            )
            snapshot = tracker.snapshot({
                "status": "FULL_AUTONOMY_PAUSED",
                "portfolio_id": "p",
                "plan": {"target_files": ["app/demo.py"]},
                "execution": {},
            })
            self.assertEqual(snapshot["changed_files"], [])

    def test_failed_dependency_is_not_reported_as_constraints_pause(self) -> None:
        failed = type("Campaign", (), {
            "campaign_id": "failed",
            "status": "FAILED",
            "depends_on": [],
        })()
        pending = type("Campaign", (), {
            "campaign_id": "pending",
            "status": "PENDING",
            "depends_on": ["failed"],
        })()
        portfolio = type("Portfolio", (), {
            "campaigns": [failed, pending],
        })()

        self.assertEqual(
            AutonomousCampaignDirector._failed_dependency_blockers(portfolio),
            ["failed"],
        )

    def test_execute_forces_active_policy_and_clears_plan_completion(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "app").mkdir()
            (root / "tests").mkdir()
            workflow = FullAutonomyWorkflow(root)
            planned = workflow.run(
                OBJECTIVE,
                context={
                    "autonomy_run_id": "autonomy-policy-test",
                    "auto_execute": False,
                    "plan_only": True,
                },
            )
            self.assertTrue(planned["autonomy_run"]["completed_at"])

            # Avoid real execution; inspect state at resume entry through a director stub.
            class Director:
                def direct(self, portfolio_id: str, **kwargs):
                    return {
                        "success": True,
                        "status": "CAMPAIGN_DIRECTOR_PAUSED_CYCLE_LIMIT",
                        "portfolio": workflow.portfolio_workflow.get_portfolio(portfolio_id),
                        "director_run": {"run_id": "director-policy"},
                        "errors": [],
                    }

            workflow.director = Director()
            result = workflow.execute(
                planned["autonomy_run_id"],
                context={"auto_execute": False},
            )
            saved = workflow.store.get(planned["autonomy_run_id"])
            self.assertTrue(saved["policy"]["auto_execute"])
            self.assertEqual(saved["completed_at"], "")
            self.assertEqual(result["status"], "FULL_AUTONOMY_PAUSED")

    def test_real_full_autonomy_completes_in_isolated_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "app/gui").mkdir(parents=True)
            (root / "tests").mkdir()
            (root / "app/__init__.py").write_text("", encoding="utf-8")
            (root / "app/gui/__init__.py").write_text("", encoding="utf-8")
            (root / "app/gui/main_window.py").write_text(
                "class MainWindow:\n    pass\n",
                encoding="utf-8",
            )
            workflow = FullAutonomyWorkflow(root)
            plan = workflow.run(
                OBJECTIVE,
                context={
                    "autonomy_run_id": "autonomy-e2e-b5161",
                    "auto_execute": False,
                    "plan_only": True,
                    "auto_approve": True,
                },
            )
            result = workflow.execute(
                plan["autonomy_run_id"],
                context={
                    "auto_approve": True,
                    "auto_rollback": True,
                    "final_validation": True,
                    "max_cycles": 10,
                },
            )

            self.assertTrue(result["success"])
            self.assertEqual(result["status"], "FULL_AUTONOMY_COMPLETED")
            self.assertEqual(result["execution"]["progress_percent"], 100.0)
            self.assertEqual(len(result["execution"]["changed_files"]), 6)
            self.assertTrue((root / "app/autonomy_demo/service.py").is_file())
            self.assertTrue((root / "tests/test_autonomy_demo_feature.py").is_file())


if __name__ == "__main__":
    unittest.main()
