from __future__ import annotations

import hashlib
import os
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from app.autodev.developer_controller import (
    DeveloperController,
)
from app.autodev.execution_guard import (
    ExecutionGuard,
)
from app.autodev.execution_policy import (
    ExecutionPolicy,
    ProjectBoundaryPolicy,
)
from app.autodev.safe_patch_builder import (
    SafePatchBuilder,
)
from app.autodev.safe_patch_executor import (
    SafePatchExecutionPolicy,
    SafePatchExecutor,
)


class AuditA43ExecutionPolicyTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)
        self.target = self.root / "app/sample.py"
        self.target.parent.mkdir(
            parents=True,
        )
        self.target.write_text(
            "VALUE = 1\n",
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def guard(
        self,
        **kwargs,
    ) -> ExecutionGuard:
        return ExecutionGuard(
            policy=ExecutionPolicy(
                project_root=self.root,
                **kwargs,
            )
        )

    def valid_validation(self) -> dict:
        return {
            "success": True,
            "status": "VALID",
        }

    def patch(self):
        return SafePatchBuilder(
            project_root=str(
                self.root
            )
        ).build(
            path="app/sample.py",
            new_content="VALUE = 2\n",
            goal="Update sample",
        )

    def test_relative_target_is_resolved_from_project_root(
        self,
    ) -> None:
        original = Path.cwd()

        with tempfile.TemporaryDirectory() as other:
            os.chdir(other)

            try:
                decision = self.guard().evaluate(
                    task={
                        "target": "app/sample.py",
                    },
                    validation=self.valid_validation(),
                    approved=True,
                )
            finally:
                os.chdir(original)

        self.assertTrue(
            decision.allowed
        )
        self.assertEqual(
            Path(
                decision.targets[0]
            ),
            self.target.resolve(),
        )

    def test_guard_requires_explicit_validation(
        self,
    ) -> None:
        decision = self.guard().evaluate(
            task={
                "target": self.target,
            },
            approved=True,
        )

        self.assertFalse(
            decision.allowed
        )
        self.assertEqual(
            decision.status,
            "EXECUTION_BLOCKED",
        )
        self.assertIn(
            "Brak wyniku walidacji wykonania.",
            decision.errors,
        )

    def test_guard_rejects_non_boolean_approval(
        self,
    ) -> None:
        decision = self.guard().evaluate(
            task={
                "target": self.target,
            },
            validation=self.valid_validation(),
            approved="yes",
        )

        self.assertFalse(
            decision.allowed
        )
        self.assertEqual(
            decision.status,
            "WAITING_FOR_APPROVAL",
        )

    def test_automatic_approval_obeys_risk_limit(
        self,
    ) -> None:
        decision = self.guard(
            max_auto_approval_risk=10.0,
        ).evaluate(
            task={
                "target": self.target,
            },
            prediction={
                "risk_score": 11.0,
                "risk_level": "MEDIUM",
            },
            validation=self.valid_validation(),
            approved=True,
            automatic=True,
        )

        self.assertFalse(
            decision.allowed
        )
        self.assertIn(
            "Ryzyko przekracza limit automatycznej "
            "akceptacji.",
            decision.errors,
        )

    def test_protected_project_file_is_blocked(
        self,
    ) -> None:
        protected = self.root / ".env"
        protected.write_text(
            "SECRET=value\n",
            encoding="utf-8",
        )
        decision = self.guard().evaluate(
            task={
                "target": protected,
            },
            validation=self.valid_validation(),
            approved=True,
        )

        self.assertFalse(
            decision.allowed
        )
        self.assertTrue(
            any(
                "chronion" in error.casefold()
                for error in decision.errors
            )
        )

    def test_symlink_target_is_blocked(
        self,
    ) -> None:
        link = self.root / "app/link.py"

        try:
            link.symlink_to(
                self.target
            )
        except (
            OSError,
            NotImplementedError,
        ):
            self.skipTest(
                "System nie pozwala utworzyć symlinka."
            )

        decision = self.guard().evaluate(
            task={
                "target": link,
            },
            validation=self.valid_validation(),
            approved=True,
        )

        self.assertFalse(
            decision.allowed
        )

    def test_validator_rejects_tampered_patch_hash(
        self,
    ) -> None:
        patch_value = self.patch()
        patch_value.new_hash = hashlib.sha256(
            b"tampered"
        ).hexdigest()

        executor = SafePatchExecutor(
            policy=SafePatchExecutionPolicy(
                project_root=self.root,
                dry_run=True,
                run_unit_tests=False,
            )
        )
        result = executor.execute(
            patch_value,
            approved=True,
        )

        self.assertFalse(
            result.success
        )
        self.assertEqual(
            result.status,
            "VALIDATION_FAILED",
        )

    def test_patch_cannot_bypass_approval_policy(
        self,
    ) -> None:
        patch_value = self.patch()
        patch_value.requires_approval = False
        executor = SafePatchExecutor(
            policy=SafePatchExecutionPolicy(
                project_root=self.root,
                dry_run=True,
                require_approval=False,
                run_unit_tests=False,
            )
        )

        result = executor.execute(
            patch_value,
            approved=False,
        )

        self.assertFalse(
            result.success
        )
        self.assertEqual(
            result.status,
            "WAITING_FOR_APPROVAL",
        )

    def test_backup_root_outside_project_is_rejected(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as other:
            with self.assertRaises(
                ValueError
            ):
                SafePatchExecutor(
                    policy=SafePatchExecutionPolicy(
                        project_root=self.root,
                        backup_root=other,
                    )
                )

    def test_approved_dry_run_remains_compatible(
        self,
    ) -> None:
        executor = SafePatchExecutor(
            policy=SafePatchExecutionPolicy(
                project_root=self.root,
                dry_run=True,
                run_unit_tests=False,
            )
        )

        result = executor.execute(
            self.patch(),
            approved=True,
        )

        self.assertTrue(
            result.success
        )
        self.assertEqual(
            result.status,
            "DRY_RUN_OK",
        )
        self.assertEqual(
            self.target.read_text(
                encoding="utf-8",
            ),
            "VALUE = 1\n",
        )

    def test_controller_blocks_high_risk_auto_approval(
        self,
    ) -> None:
        controller = DeveloperController.__new__(
            DeveloperController
        )
        controller.execution_guard = self.guard(
            max_auto_approval_risk=10.0,
        )
        transaction = SimpleNamespace(
            metadata={
                "risk_score": 30.0,
                "risk_level": "HIGH",
            },
            files=lambda: [
                str(self.target),
            ],
            validate=lambda: (
                True,
                [],
            ),
        )
        controller.session = MagicMock()
        controller.session.has_transaction.return_value = True
        controller.session.status = (
            "waiting_for_approval"
        )
        controller.session.transaction = transaction
        controller.last_result = None

        result = controller.approve(
            automatic=True
        )

        self.assertFalse(
            result.success
        )
        self.assertEqual(
            result.status,
            "automatic_approval_blocked",
        )
        controller.session.approve.assert_not_called()


if __name__ == "__main__":
    unittest.main()
