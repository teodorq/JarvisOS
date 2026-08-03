from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock

from app.autodev.change_transaction import (
    ChangeTransaction,
)
from app.autodev.developer_executor import (
    DeveloperExecutor,
)
from app.autodev.execution_result import (
    ExecutionResult,
)


class B5154WindowsRollbackHotfixTests(
    unittest.TestCase
):

    def test_rollback_last_uses_snapshot_fallback(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            first = root / "app/alpha.py"
            second = root / "app/beta.py"
            first.parent.mkdir(
                parents=True,
                exist_ok=True,
            )
            first.write_text(
                "VALUE = 10\n",
                encoding="utf-8",
            )
            second.write_text(
                "VALUE = 20\n",
                encoding="utf-8",
            )

            transaction = ChangeTransaction(
                goal="Refaktoryzacja dwóch plików",
                target="multi_file_refactor",
            )
            transaction.add_change(
                str(first),
                "VALUE = 1\n",
                "VALUE = 10\n",
            )
            transaction.add_change(
                str(second),
                "VALUE = 2\n",
                "VALUE = 20\n",
            )
            transaction.mark_validated()

            executor = DeveloperExecutor(
                project_root=root,
                run_tests=False,
            )
            executor.last_transaction = transaction
            executor.rollback_manager.rollback = MagicMock(
                return_value=ExecutionResult(
                    success=False,
                    step_name="rollback",
                    message=(
                        "Symulowana blokada pliku Windows."
                    ),
                    errors=[
                        "PermissionError: plik zablokowany",
                    ],
                )
            )

            result = executor.rollback_last()

            self.assertTrue(
                result.success
            )
            self.assertEqual(
                result.step_name,
                "rollback_fallback",
            )
            self.assertTrue(
                result.data["fallback"]
            )
            self.assertIn(
                "primary_rollback_errors",
                result.data,
            )
            self.assertEqual(
                first.read_text(
                    encoding="utf-8",
                ),
                "VALUE = 1\n",
            )
            self.assertEqual(
                second.read_text(
                    encoding="utf-8",
                ),
                "VALUE = 2\n",
            )
            self.assertEqual(
                transaction.status,
                "rolled_back",
            )

    def test_successful_primary_rollback_is_preserved(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            executor = DeveloperExecutor(
                project_root=root,
                run_tests=False,
            )
            transaction = ChangeTransaction(
                goal="Test",
            )
            executor.last_transaction = transaction
            expected = ExecutionResult(
                success=True,
                step_name="rollback",
                message="OK",
            )
            executor.rollback_manager.rollback = MagicMock(
                return_value=expected
            )
            executor._restore_transaction_snapshot = MagicMock()

            result = executor.rollback_last()

            self.assertIs(
                result,
                expected,
            )
            executor._restore_transaction_snapshot.assert_not_called()


if __name__ == "__main__":
    unittest.main()
