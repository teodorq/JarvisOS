from __future__ import annotations

import unittest

from app.ai.software_engineer import (
    ExecutionRecoveryOrchestrator,
    ExecutionRecoveryPolicy,
)


def completed_result() -> dict:
    return {
        "success": True,
        "status": "COMPLETED",
        "workflow": {
            "success": True,
            "status": "completed",
            "data": {
                "rollback_attempted": False,
                "rollback_success": False,
            },
        },
    }


def failed_result(
    *,
    category: str = "SYNTAX",
    retryable: bool = True,
    rollback_attempted: bool = True,
    rollback_success: bool = True,
) -> dict:
    return {
        "success": False,
        "status": "FAILED_AND_ROLLED_BACK",
        "errors": [
            "validation failed",
        ],
        "workflow": {
            "success": False,
            "status": "failed_and_rolled_back",
            "errors": [
                "workflow failed",
            ],
            "data": {
                "rollback_attempted": (
                    rollback_attempted
                ),
                "rollback_success": (
                    rollback_success
                ),
                "failure_analysis": {
                    "category": category,
                    "retryable": retryable,
                    "message": "Testy nie przeszły.",
                    "errors": [
                        "AssertionError",
                    ],
                },
            },
        },
    }


class FakeImplementationExecutor:

    def __init__(
        self,
        results: list[dict],
    ) -> None:
        self.results = list(results)
        self.calls: list[dict] = []

    def execute(
        self,
        task,
        *,
        auto_approve: bool,
        auto_rollback: bool,
    ):
        self.calls.append(
            {
                "task": task,
                "auto_approve": auto_approve,
                "auto_rollback": auto_rollback,
            }
        )

        if not self.results:
            raise AssertionError(
                "Brak przygotowanego wyniku."
            )

        return self.results.pop(0)


class ExecutionRecoveryTests(unittest.TestCase):

    def task(self) -> dict:
        return {
            "task_id": "task-1",
            "title": "Update module",
            "category": "implementation",
            "payload": {
                "description": "Update module safely.",
                "path": "app/sample.py",
                "proposed_content": "VALUE = 2\n",
                "metadata": {},
            },
        }

    def test_completed_execution_does_not_retry(self) -> None:
        executor = FakeImplementationExecutor(
            [
                completed_result(),
            ]
        )

        result = ExecutionRecoveryOrchestrator(
            implementation_executor=executor,
        ).execute_with_recovery(
            self.task()
        )

        self.assertTrue(result["success"])
        self.assertEqual(
            result["status"],
            "COMPLETED",
        )
        self.assertEqual(
            result["attempt_count"],
            1,
        )

    def test_retryable_failure_retries_and_succeeds(self) -> None:
        executor = FakeImplementationExecutor(
            [
                failed_result(
                    category="TEST_FAILURE",
                ),
                completed_result(),
            ]
        )

        result = ExecutionRecoveryOrchestrator(
            implementation_executor=executor,
        ).execute_with_recovery(
            self.task()
        )

        self.assertTrue(result["success"])
        self.assertTrue(result["retry_used"])
        self.assertTrue(
            result["rollback_used"]
        )
        self.assertEqual(
            result["attempt_count"],
            2,
        )

    def test_retry_removes_old_proposed_content(self) -> None:
        executor = FakeImplementationExecutor(
            [
                failed_result(),
                completed_result(),
            ]
        )

        ExecutionRecoveryOrchestrator(
            implementation_executor=executor,
        ).execute_with_recovery(
            self.task()
        )

        retry_task = executor.calls[1]["task"]
        payload = retry_task["payload"]

        self.assertNotIn(
            "proposed_content",
            payload,
        )
        self.assertIn(
            "POPRZEDNIA PRÓBA",
            payload["description"],
        )
        self.assertIn(
            "recovery",
            payload["metadata"],
        )

    def test_non_retryable_failure_stops_immediately(self) -> None:
        executor = FakeImplementationExecutor(
            [
                failed_result(
                    category="PERMISSION",
                    retryable=False,
                ),
                completed_result(),
            ]
        )

        result = ExecutionRecoveryOrchestrator(
            implementation_executor=executor,
        ).execute_with_recovery(
            self.task()
        )

        self.assertFalse(result["success"])
        self.assertEqual(
            result["status"],
            "NON_RETRYABLE_FAILURE",
        )
        self.assertEqual(
            result["attempt_count"],
            1,
        )

    def test_failed_rollback_stops_retry(self) -> None:
        executor = FakeImplementationExecutor(
            [
                failed_result(
                    rollback_attempted=True,
                    rollback_success=False,
                ),
                completed_result(),
            ]
        )

        result = ExecutionRecoveryOrchestrator(
            implementation_executor=executor,
        ).execute_with_recovery(
            self.task()
        )

        self.assertEqual(
            result["status"],
            "ROLLBACK_FAILED",
        )
        self.assertEqual(
            result["attempt_count"],
            1,
        )

    def test_retry_limit_is_enforced(self) -> None:
        executor = FakeImplementationExecutor(
            [
                failed_result(),
                failed_result(),
            ]
        )

        result = ExecutionRecoveryOrchestrator(
            implementation_executor=executor,
            policy=ExecutionRecoveryPolicy(
                max_attempts=2,
            ),
        ).execute_with_recovery(
            self.task()
        )

        self.assertFalse(result["success"])
        self.assertEqual(
            result["status"],
            "RETRY_EXHAUSTED",
        )
        self.assertEqual(
            result["attempt_count"],
            2,
        )

    def test_preview_ready_stops_without_retry(self) -> None:
        executor = FakeImplementationExecutor(
            [
                {
                    "success": True,
                    "status": "PREVIEW_READY",
                    "workflow": {
                        "success": True,
                        "status": (
                            "waiting_for_approval"
                        ),
                    },
                }
            ]
        )

        result = ExecutionRecoveryOrchestrator(
            implementation_executor=executor,
        ).execute_with_recovery(
            self.task()
        )

        self.assertEqual(
            result["status"],
            "COMPLETED",
        )
        self.assertEqual(
            result["attempt_count"],
            1,
        )

    def test_policy_passes_autonomous_flags(self) -> None:
        executor = FakeImplementationExecutor(
            [
                completed_result(),
            ]
        )

        ExecutionRecoveryOrchestrator(
            implementation_executor=executor,
            policy=ExecutionRecoveryPolicy(
                auto_approve=False,
                auto_rollback=True,
            ),
        ).execute_with_recovery(
            self.task()
        )

        self.assertFalse(
            executor.calls[0]["auto_approve"]
        )
        self.assertTrue(
            executor.calls[0]["auto_rollback"]
        )

    def test_invalid_task_is_rejected(self) -> None:
        executor = FakeImplementationExecutor(
            [
                completed_result(),
            ]
        )

        result = ExecutionRecoveryOrchestrator(
            implementation_executor=executor,
        ).execute_with_recovery(
            object()
        )

        self.assertEqual(
            result["status"],
            "INVALID_SCHEDULED_TASK",
        )
        self.assertEqual(
            len(executor.calls),
            0,
        )


if __name__ == "__main__":
    unittest.main()
