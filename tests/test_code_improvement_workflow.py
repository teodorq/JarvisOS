import unittest
from unittest.mock import MagicMock

from app.autodev.code_improvement_workflow import (
    CodeImprovementWorkflow,
)


class TestCodeImprovementWorkflow(
    unittest.TestCase
):

    def setUp(
        self,
    ) -> None:

        self.workflow = CodeImprovementWorkflow(
            project_root="C:/JarvisAI"
        )

    def test_no_tasks(
        self,
    ) -> None:

        result = self.workflow.run(
            []
        )

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "NO_TASKS"
        )

    def test_full_workflow(
        self,
    ) -> None:

        selected_task = {
            "title": "Improve Brain",
            "description": "Review Brain",
        }

        module_analysis = {
            "success": True,
            "files": [
                "C:/JarvisAI/app/ai/brain.py",
            ],
        }

        target = {
            "path": "C:/JarvisAI/app/ai/brain.py",
            "score": 100,
        }

        issue_analysis = {
            "success": True,
            "issues": [
                {
                    "type": "LONG_FUNCTION",
                    "severity": "NORMAL",
                    "score": 25,
                    "line": 10,
                    "message": "Long function",
                }
            ],
        }

        plan = {
            "success": True,
            "status": "PLAN_READY",
            "path": target["path"],
            "requires_code_generation": True,
        }

        self.workflow.improvement_selector.select = (
            MagicMock(
                return_value=selected_task
            )
        )

        self.workflow.engine.analyze_task = (
            MagicMock(
                return_value=module_analysis
            )
        )

        self.workflow.target_selector.select = (
            MagicMock(
                return_value=target
            )
        )

        self.workflow.issue_analyzer.analyze = (
            MagicMock(
                return_value=issue_analysis
            )
        )

        self.workflow.planner.build_plan = (
            MagicMock(
                return_value=plan
            )
        )

        result = self.workflow.run(
            [
                selected_task
            ]
        )

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "PLAN_READY"
        )

        self.assertEqual(
            result["target"],
            target
        )

        self.assertEqual(
            result["plan"],
            plan
        )

    def test_module_analysis_failure(
        self,
    ) -> None:

        task = {
            "title": "Improve AutoDev",
        }

        self.workflow.improvement_selector.select = (
            MagicMock(
                return_value=task
            )
        )

        self.workflow.engine.analyze_task = (
            MagicMock(
                return_value={
                    "success": False,
                    "status": "TARGET_NOT_FOUND",
                }
            )
        )

        result = self.workflow.run(
            [
                task
            ]
        )

        self.assertFalse(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "MODULE_ANALYSIS_FAILED"
        )


if __name__ == "__main__":
    unittest.main()