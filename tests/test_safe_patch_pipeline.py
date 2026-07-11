import tempfile
import unittest
from pathlib import Path

from app.autodev.safe_patch_builder import (
    SafePatchBuilder,
)
from app.autodev.safe_patch_executor import (
    SafePatchExecutionPolicy,
    SafePatchExecutor,
)
from app.autodev.safe_patch_validator import (
    SafePatchValidator,
)


class TestSafePatchPipeline(
    unittest.TestCase
):

    def setUp(
        self,
    ) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

        self.target = self.root / "sample.py"
        self.target.write_text(
            "def value():\n"
            "    return 1\n",
            encoding="utf-8",
        )

    def tearDown(
        self,
    ) -> None:
        self.temp_dir.cleanup()

    def test_builds_patch_without_writing(
        self,
    ) -> None:
        builder = SafePatchBuilder(
            project_root=str(self.root)
        )

        patch = builder.build(
            path="sample.py",
            new_content=(
                "def value():\n"
                "    return 2\n"
            ),
            goal="Zmiana wartości",
        )

        self.assertTrue(
            patch.requires_approval
        )

        self.assertEqual(
            self.target.read_text(
                encoding="utf-8"
            ),
            "def value():\n"
            "    return 1\n",
        )

    def test_validator_blocks_eval(
        self,
    ) -> None:
        builder = SafePatchBuilder(
            project_root=str(self.root)
        )

        patch = builder.build(
            path="sample.py",
            new_content=(
                "def value():\n"
                "    return eval('2')\n"
            ),
        )

        validator = SafePatchValidator(
            project_root=str(self.root)
        )

        result = validator.validate(
            patch
        )

        self.assertFalse(
            result.success
        )

    def test_executor_dry_run_does_not_write(
        self,
    ) -> None:
        builder = SafePatchBuilder(
            project_root=str(self.root)
        )

        patch = builder.build(
            path="sample.py",
            new_content=(
                "def value():\n"
                "    return 2\n"
            ),
        )

        executor = SafePatchExecutor(
            policy=SafePatchExecutionPolicy(
                project_root=str(self.root),
                dry_run=True,
                run_unit_tests=False,
            )
        )

        result = executor.execute(
            patch,
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
                encoding="utf-8"
            ),
            "def value():\n"
            "    return 1\n",
        )


if __name__ == "__main__":
    unittest.main()
