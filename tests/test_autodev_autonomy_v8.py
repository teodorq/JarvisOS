import unittest
from unittest.mock import MagicMock

from app.autodev.autodev_autonomy_v8 import (
    AutoDevAutonomyV8,
)
from app.autodev.autodev_queue_service import (
    AutoDevQueueService,
)


class TestAutoDevAutonomyV8(
    unittest.TestCase
):

    def _ready_gate(self) -> dict:
        return {
            "success": True,
            "status": "AUTONOMY_V7_READY",
            "goal": {
                "goal": "Ulepsz pamięć",
                "priority_score": 20,
                "risk_score": 10,
            },
            "decision": {
                "allowed": True,
                "status": "PREVIEW_ALLOWED",
                "action": "QUEUE_AND_PREVIEW",
                "requires_approval": True,
            },
            "requires_approval": True,
            "cycle": {
                "cycle": {
                    "cycle": {
                        "preview": {
                            "status": "EXECUTION_PREVIEW_READY",
                            "steps": [
                                {
                                    "order": 1,
                                    "title": "Analiza",
                                }
                            ],
                            "writes_code": False,
                        }
                    }
                }
            },
            "writes_code": False,
        }

    def test_creates_pending_approval_request(
        self,
    ) -> None:
        autonomy_v7 = MagicMock()
        autonomy_v7.run.return_value = self._ready_gate()

        autonomy = AutoDevAutonomyV8(
            autonomy_v7=autonomy_v7
        )

        result = autonomy.run()

        self.assertTrue(result["success"])
        self.assertEqual(
            result["status"],
            "AUTONOMY_V8_PENDING_APPROVAL",
        )
        self.assertEqual(
            result["request"]["request_id"],
            "autodev-v8-0001",
        )
        self.assertEqual(
            result["request"]["preview"]["status"],
            "EXECUTION_PREVIEW_READY",
        )
        self.assertFalse(result["writes_code"])
        self.assertEqual(
            autonomy.status()["pending_count"],
            1,
        )

    def test_approve_moves_request_to_queue(
        self,
    ) -> None:
        autonomy_v7 = MagicMock()
        autonomy_v7.run.return_value = self._ready_gate()
        queue = AutoDevQueueService()
        autonomy = AutoDevAutonomyV8(
            autonomy_v7=autonomy_v7,
            queue_service=queue,
        )

        pending = autonomy.run()
        request_id = pending["request"]["request_id"]
        result = autonomy.approve(request_id)

        self.assertTrue(result["success"])
        self.assertTrue(result["approved"])
        self.assertTrue(result["queued"])
        self.assertFalse(result["writes_code"])
        self.assertEqual(queue.status()["count"], 1)
        self.assertEqual(
            autonomy.status()["pending_count"],
            0,
        )

    def test_reject_removes_pending_request(
        self,
    ) -> None:
        autonomy_v7 = MagicMock()
        autonomy_v7.run.return_value = self._ready_gate()
        autonomy = AutoDevAutonomyV8(
            autonomy_v7=autonomy_v7
        )

        pending = autonomy.run()
        request_id = pending["request"]["request_id"]
        result = autonomy.reject(
            request_id,
            reason="Wymaga dalszej analizy",
        )

        self.assertEqual(
            result["status"],
            "AUTONOMY_V8_REJECTED",
        )
        self.assertEqual(
            result["request"]["rejection_reason"],
            "Wymaga dalszej analizy",
        )
        self.assertEqual(
            autonomy.status()["pending_count"],
            0,
        )

    def test_blocked_decision_is_not_queued(
        self,
    ) -> None:
        autonomy_v7 = MagicMock()
        gate = self._ready_gate()
        gate["decision"] = {
            "allowed": False,
            "status": "RISK_BLOCKED",
            "requires_approval": True,
        }
        autonomy_v7.run.return_value = gate
        autonomy = AutoDevAutonomyV8(
            autonomy_v7=autonomy_v7
        )

        result = autonomy.run()

        self.assertEqual(
            result["status"],
            "DECISION_BLOCKED",
        )
        self.assertFalse(result["queued"])
        self.assertEqual(
            autonomy.status()["pending_count"],
            0,
        )


if __name__ == "__main__":
    unittest.main()
