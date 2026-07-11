import unittest
from unittest.mock import MagicMock

from app.autodev.autodev_intelligence_orchestrator import (
    AutoDevIntelligenceOrchestrator,
)


class TestAutoDevIntelligenceOrchestrator(
    unittest.TestCase
):

    def setUp(
        self,
    ) -> None:

        self.intelligence = MagicMock()
        self.pipeline = MagicMock()

        self.orchestrator = (
            AutoDevIntelligenceOrchestrator(
                intelligence=self.intelligence,
                improvement_pipeline=self.pipeline,
            )
        )

    def test_analyze_only(
        self,
    ) -> None:

        self.intelligence.run_cycle.return_value = {
            "success": True,
            "status": "INTELLIGENCE_V2_COMPLETED",
            "selected": None,
            "base_cycle": {
                "recommendations": []
            },
        }

        result = self.orchestrator.analyze()

        self.assertTrue(
            result["success"]
        )

        self.assertFalse(
            result["writes_code"]
        )

        self.assertFalse(
            result["approved"]
        )

    def test_preview_selected_task(
        self,
    ) -> None:

        task = {
            "task_id": "task-1",
            "target": "C:/JarvisAI/app/test.py",
        }

        self.intelligence.run_cycle.return_value = {
            "success": True,
            "status": "INTELLIGENCE_V2_COMPLETED",
            "selected": {
                "task": task,
                "decision": "READY_FOR_SAFE_GENERATION",
                "predicted_risk": 20.0,
            },
            "base_cycle": {
                "recommendations": []
            },
        }

        self.pipeline.run.return_value = {
            "success": True,
            "status": "DRY_RUN_OK",
        }

        result = self.orchestrator.preview_selected()

        self.assertEqual(
            result["status"],
            "DRY_RUN_OK"
        )

        self.assertFalse(
            result["approved"]
        )

        self.assertFalse(
            result["writes_code"]
        )

        self.pipeline.run.assert_called_once_with(
            [
                task
            ],
            approved=False,
        )

    def test_high_risk_is_blocked(
        self,
    ) -> None:

        self.intelligence.run_cycle.return_value = {
            "success": True,
            "status": "INTELLIGENCE_V2_COMPLETED",
            "selected": {
                "task": {
                    "task_id": "task-2",
                    "target": "C:/JarvisAI/app/risky.py",
                },
                "decision": "PREVIEW_ONLY",
                "predicted_risk": 90.0,
            },
            "base_cycle": {
                "recommendations": []
            },
        }

        result = self.orchestrator.preview_selected()

        self.assertEqual(
            result["status"],
            "RISK_BLOCKED"
        )

        self.pipeline.run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
