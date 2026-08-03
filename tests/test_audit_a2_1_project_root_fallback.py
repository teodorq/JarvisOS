from __future__ import annotations

import unittest
from pathlib import Path

from app.ai.brain import Brain


class AuditA21ProjectRootFallbackTests(unittest.TestCase):

    def test_project_root_exists_without_constructor(self) -> None:
        brain = Brain.__new__(
            Brain
        )

        root = brain.project_root

        self.assertTrue(root)
        self.assertTrue(
            Path(root).is_absolute()
        )

    def test_project_root_setter_normalizes_value(self) -> None:
        brain = Brain.__new__(
            Brain
        )

        brain.project_root = "."

        self.assertTrue(
            Path(
                brain.project_root
            ).is_absolute()
        )

    def test_repeated_access_uses_cached_value(self) -> None:
        brain = Brain.__new__(
            Brain
        )

        first = brain.project_root
        second = brain.project_root

        self.assertEqual(
            first,
            second,
        )
        self.assertEqual(
            brain._project_root,
            first,
        )


if __name__ == "__main__":
    unittest.main()
