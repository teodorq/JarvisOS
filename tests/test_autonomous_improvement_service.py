import unittest
from unittest.mock import MagicMock

from app.autodev.autonomous_improvement_controller import (
    AutonomousImprovementController,
)
from app.autodev.autonomous_improvement_service import (
    AutonomousImprovementService,
)


class TestAutonomousImprovementService(
    unittest.TestCase
):

    def setUp(
        self,
    ) -> None:

        self.autodev_pipeline = MagicMock()
        self.improvement_pipeline = MagicMock()

        self.service = AutonomousImprovementService(
            autodev_pipeline=(
                self.autodev_pipeline
            ),
            improvement_pipeline=(
                self.improvement_pipeline
            ),
        )

        self.controller = (
            AutonomousImprovementController(
                service=self.service
            )
        )

    def test_collects_only_active_tasks(
        self,
    ) -> None:

        self.autodev_pipeline.list_tasks.return_value = [
            {
                "task_id": "1",
                "status": "PENDING",
            },
            {
                "task_id": "2",
                "status": "COMPLETED",
            },
        ]

        tasks = self.service.collect_tasks()

        self.assertEqual(
            len(tasks),
            1
        )

        self.assertEqual(
            tasks[0]["task_id"],
            "1"
        )

    def test_preview_is_not_approved(
        self,
    ) -> None:

        self.autodev_pipeline.list_tasks.return_value = [
            {
                "task_id": "1",
                "status": "PENDING",
            }
        ]

        self.improvement_pipeline.run.return_value = {
            "success": True,
            "status": "DRY_RUN_OK",
        }

        result = self.service.preview()

        self.assertFalse(
            result["approved"]
        )

        self.improvement_pipeline.run.assert_called_once_with(
            [
                {
                    "task_id": "1",
                    "status": "PENDING",
                }
            ],
            approved=False,
        )

    def test_controller_status(
        self,
    ) -> None:

        self.autodev_pipeline.status.return_value = {
            "state": "STOPPED"
        }

        self.improvement_pipeline.status.return_value = {
            "ready": True
        }

        result = self.controller.handle(
            "status autonomicznego ulepszania"
        )

        self.assertTrue(
            result["success"]
        )

        self.assertEqual(
            result["status"],
            "AUTONOMOUS_IMPROVEMENT_STATUS"
        )


if __name__ == "__main__":
    unittest.main()
