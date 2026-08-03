from __future__ import annotations

import unittest

from app.autonomy_learning_demo_4 import (
    AutonomyLearningDemo4Controller,
    AutonomyLearningDemo4Request,
    AutonomyLearningDemo4Service,
)


class AutonomyLearningDemo4FeatureTests(unittest.TestCase):

    def test_service_executes_request(
        self,
    ) -> None:
        result = AutonomyLearningDemo4Service().execute(
            AutonomyLearningDemo4Request(
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
        result = AutonomyLearningDemo4Controller().handle(
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
