from __future__ import annotations

import unittest

from app.autonomy_learning_demo import (
    AutonomyLearningDemoController,
    AutonomyLearningDemoRequest,
    AutonomyLearningDemoService,
)


class AutonomyLearningDemoFeatureTests(unittest.TestCase):

    def test_service_executes_request(
        self,
    ) -> None:
        result = AutonomyLearningDemoService().execute(
            AutonomyLearningDemoRequest(
                payload={
                    "value": 1,
                }
            )
        )

        self.assertTrue(
            result.success
        )
        self.assertEqual(
            result.status,
            "COMPLETED",
        )
        self.assertEqual(
            result.data["payload"]["value"],
            1,
        )

    def test_controller_rejects_unknown_command(
        self,
    ) -> None:
        result = AutonomyLearningDemoController().handle(
            "nieznane polecenie"
        )

        self.assertFalse(
            result.success
        )
        self.assertEqual(
            result.status,
            "UNSUPPORTED_COMMAND",
        )


if __name__ == "__main__":
    unittest.main()
