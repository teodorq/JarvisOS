import unittest
from unittest.mock import MagicMock

from app.autodev.autonomous_improvement_pipeline import (
    AutonomousImprovementPipeline,
    AutonomousImprovementPolicy,
)


class TestAutonomousImprovementPipeline(
    unittest.TestCase
):

    def setUp(
        self,
    ) -> None:

        self.workflow = MagicMock()
        self.builder = MagicMock()
        self.validator = MagicMock()
        self.executor = MagicMock()
        self.memory = MagicMock()

        self.pipeline = (
            AutonomousImprovementPipeline(
                policy=AutonomousImprovementPolicy(
                    dry_run=True
                ),
                workflow=self.workflow,
                builder=self.builder,
                validator=self.validator,
                executor=self.executor,
                memory=self.memory,
            )
        )

    def test_no_tasks(
        self,
    ) -> None:

        self.workflow.run.return_value = {
            "success": True,
            "status": "NO_TASKS",
            "selected_task": None,
        }

        result = self.pipeline.run(
            []
        )

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "NO_TASKS"
        )

    def test_no_candidate(
        self,
    ) -> None:

        self.workflow.run.return_value = {
            "success": True,
            "status": "PLAN_READY",
            "selected_task": {
                "title": "Improve Brain"
            },
            "candidate": None,
        }

        result = self.pipeline.run(
            [
                {
                    "title": "Improve Brain"
                }
            ]
        )

        self.assertFalse(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "NO_CANDIDATE"
        )

    def test_dry_run_pipeline(
        self,
    ) -> None:

        task = {
            "title": "Improve Brain"
        }

        candidate = {
            "success": True,
            "status": "CANDIDATE_READY",
            "path": (
                "C:/JarvisAI/app/ai/brain.py"
            ),
            "proposed_content": "print('ok')\n",
            "goal": "Safe change",
        }

        self.workflow.run.return_value = {
            "success": True,
            "status": "CANDIDATE_READY",
            "selected_task": task,
            "candidate": candidate,
        }

        patch = MagicMock()
        patch.to_dict.return_value = {
            "patch_id": "patch-1"
        }

        self.builder.build.return_value = patch

        validation = MagicMock()
        validation.success = True
        validation.to_dict.return_value = {
            "success": True,
            "status": "VALID",
        }

        self.validator.validate.return_value = (
            validation
        )

        execution = MagicMock()
        execution.success = True
        execution.status = "DRY_RUN_OK"
        execution.to_dict.return_value = {
            "success": True,
            "status": "DRY_RUN_OK",
        }

        self.executor.execute.return_value = (
            execution
        )

        result = self.pipeline.run(
            [
                task
            ],
            approved=True,
        )

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "DRY_RUN_OK"
        )

        self.builder.build.assert_called_once()
        self.validator.validate.assert_called_once()
        self.executor.execute.assert_called_once()


if __name__ == "__main__":
    unittest.main()
