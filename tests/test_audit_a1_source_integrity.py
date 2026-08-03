from __future__ import annotations

import ast
import unittest
from pathlib import Path


class ActiveSourceIntegrityTests(unittest.TestCase):

    LEGACY_PATHS = (
        "app/ai/brain_uszkodzony_backup.py",
        "app/ai/brain_autonomous_autodev.py",
        "app/ai/planner_backup.py",
        "app/ai/planner_llm_backup.py",
        "app/ai/planner/goal_scheduler_full.py",
        "app/ai/executive_ai/executive_ai___init__.py",
    )

    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parents[1]

    def test_all_active_app_python_files_parse(self) -> None:
        errors: list[str] = []

        for path in sorted(
            (self.project_root / "app").rglob("*.py")
        ):
            relative = path.relative_to(
                self.project_root
            )

            try:
                source = path.read_text(
                    encoding="utf-8"
                )
                ast.parse(
                    source,
                    filename=str(relative),
                )
            except Exception as error:
                errors.append(
                    f"{relative}: "
                    f"{type(error).__name__}: {error}"
                )

        self.assertEqual(
            errors,
            [],
            "\n".join(errors),
        )

    def test_known_legacy_files_are_not_active(self) -> None:
        found = [
            relative
            for relative in self.LEGACY_PATHS
            if (
                self.project_root
                / relative
            ).exists()
        ]

        self.assertEqual(
            found,
            [],
            (
                "Pliki historyczne powinny znajdować się "
                "w archive/audit_a1_legacy, nie w app."
            ),
        )

    def test_executive_ai_has_real_package_initializer(self) -> None:
        initializer = (
            self.project_root
            / "app/ai/executive_ai/__init__.py"
        )

        self.assertTrue(
            initializer.is_file()
        )
        self.assertGreater(
            initializer.stat().st_size,
            0,
        )


if __name__ == "__main__":
    unittest.main()
