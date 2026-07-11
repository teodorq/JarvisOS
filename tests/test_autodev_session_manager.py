import unittest
from unittest.mock import MagicMock

from app.autodev.autodev_session_manager import (
    AutoDevSessionManager,
)
from app.autodev.task_execution_planner import (
    TaskExecutionPlanner,
)


class TestAutoDevSessionManager(
    unittest.TestCase
):

    def test_task_execution_plan(
        self,
    ) -> None:

        planner = TaskExecutionPlanner()

        plan = planner.build_plan(
            {
                "task_id": "task-1",
                "title": "Refactor module",
                "target": "C:/JarvisAI/app/test.py",
            }
        )

        self.assertTrue(
            plan.success
        )

        self.assertEqual(
            plan.status,
            "PLAN_READY"
        )

        self.assertEqual(
            len(plan.steps),
            8
        )

    def test_preview_session(
        self,
    ) -> None:

        orchestrator = MagicMock()

        task = {
            "task_id": "task-1",
            "title": "Refactor module",
            "target": "C:/JarvisAI/app/test.py",
        }

        orchestrator.analyze.return_value = {
            "success": True,
            "cycle": {
                "selected": {
                    "task": task,
                    "predicted_risk": 20.0,
                    "risk_level": "LOW",
                }
            },
        }

        orchestrator.preview_selected.return_value = {
            "success": True,
            "status": "DRY_RUN_OK",
        }

        manager = AutoDevSessionManager(
            orchestrator=orchestrator
        )

        manager.guard.project_root = __import__(
            "pathlib"
        ).Path(
            "C:/JarvisAI"
        ).resolve()

        result = manager.run_preview_session()

        self.assertTrue(
            result["success"]
        )

        self.assertFalse(
            result["writes_code"]
        )

        self.assertFalse(
            result["approved"]
        )

        self.assertEqual(
            result["status"],
            "DRY_RUN_OK"
        )

    def test_no_selected_task(
        self,
    ) -> None:

        orchestrator = MagicMock()

        orchestrator.analyze.return_value = {
            "success": True,
            "cycle": {
                "selected": None
            },
        }

        manager = AutoDevSessionManager(
            orchestrator=orchestrator
        )

        result = manager.run_preview_session()

        self.assertEqual(
            result["status"],
            "NO_SELECTED_TASK"
        )

        orchestrator.preview_selected.assert_not_called()


if __name__ == "__main__":
    unittest.main()
