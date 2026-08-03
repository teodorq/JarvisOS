from __future__ import annotations

import unittest

from app.ai.brain import Brain


class AuditA21ProjectRootFormatTests(unittest.TestCase):

    def test_project_root_uses_forward_slashes(self) -> None:
        brain = Brain.__new__(
            Brain
        )
        brain._project_root = r"C:\JarvisAI"

        self.assertEqual(
            brain.project_root,
            "C:/JarvisAI",
        )

    def test_project_root_setter_normalizes_windows_path(self) -> None:
        brain = Brain.__new__(
            Brain
        )

        brain.project_root = r"C:\JarvisAI"

        self.assertEqual(
            brain.project_root,
            "C:/JarvisAI",
        )

    def test_project_root_is_stable_for_contexts(self) -> None:
        brain = Brain.__new__(
            Brain
        )
        brain._project_root = r"C:\JarvisAI"

        context = {
            "project_root": brain.project_root,
        }

        self.assertEqual(
            context["project_root"],
            "C:/JarvisAI",
        )


if __name__ == "__main__":
    unittest.main()
