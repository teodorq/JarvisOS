from __future__ import annotations

import ast
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.core.project_paths import (
    PROJECT_ROOT_ENV,
    ProjectPaths,
    resolve_project_root,
)


class AuditA2ProjectPathsTests(unittest.TestCase):

    def test_explicit_root_has_highest_priority(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            explicit = Path(temp) / "explicit"
            environment = Path(temp) / "environment"

            with patch.dict(
                os.environ,
                {
                    PROJECT_ROOT_ENV: str(
                        environment
                    ),
                },
            ):
                resolved = resolve_project_root(
                    explicit
                )

            self.assertEqual(
                resolved,
                explicit.resolve(
                    strict=False
                ),
            )

    def test_environment_root_is_supported(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            expected = Path(temp) / "jarvis"

            with patch.dict(
                os.environ,
                {
                    PROJECT_ROOT_ENV: str(
                        expected
                    ),
                },
            ):
                resolved = resolve_project_root()

            self.assertEqual(
                resolved,
                expected.resolve(
                    strict=False
                ),
            )

    def test_runtime_directories_are_created(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = ProjectPaths.from_value(
                temp
            )
            created = (
                paths.ensure_runtime_directories()
            )

            self.assertTrue(
                all(
                    path.is_dir()
                    for path in created
                )
            )
            self.assertEqual(
                paths.autodev_data,
                Path(temp).resolve()
                / "data/autodev",
            )

    def test_context_contains_resolved_paths(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            paths = ProjectPaths.from_value(
                temp
            )
            context = paths.as_context()

            self.assertEqual(
                context["project_root"],
                str(Path(temp).resolve()),
            )
            self.assertEqual(
                context["data_path"],
                str(
                    Path(temp).resolve()
                    / "data"
                ),
            )

    def test_main_orchestration_has_no_fixed_project_literal(
        self,
    ) -> None:
        project_root = Path(__file__).resolve().parents[1]
        files = (
            "app/ai/brain.py",
            "app/ai/autodev_router.py",
            "app/ai/autodev_runtime_controller.py",
            "app/ai/autonomous_dev_controller.py",
        )

        offenders: list[str] = []

        for relative in files:
            source = (
                project_root / relative
            ).read_text(
                encoding="utf-8"
            )

            if (
                "C:/JarvisAI" in source
                or "C:\\\\JarvisAI" in source
            ):
                offenders.append(
                    relative
                )

        self.assertEqual(
            offenders,
            [],
        )

    def test_modified_files_parse(self) -> None:
        project_root = Path(__file__).resolve().parents[1]
        files = (
            "app/core/project_paths.py",
            "app/ai/brain.py",
            "app/ai/autodev_router.py",
            "app/ai/autodev_runtime_controller.py",
            "app/ai/autonomous_dev_controller.py",
        )

        errors: list[str] = []

        for relative in files:
            try:
                source = (
                    project_root / relative
                ).read_text(
                    encoding="utf-8"
                )
                ast.parse(
                    source,
                    filename=relative,
                )
            except Exception as error:
                errors.append(
                    f"{relative}: {error}"
                )

        self.assertEqual(
            errors,
            [],
            "\n".join(errors),
        )


if __name__ == "__main__":
    unittest.main()
