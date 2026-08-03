from __future__ import annotations

import unittest

from app.autonomy_demo import (
    AutonomyDemoController,
    AutonomyDemoRequest,
    AutonomyDemoService,
)


class AutonomyDemoFeatureTests(unittest.TestCase):

    def test_service_executes_request(
        self,
    ) -> None:
        result = AutonomyDemoService().execute(
            AutonomyDemoRequest(
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
        result = AutonomyDemoController().handle(
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
