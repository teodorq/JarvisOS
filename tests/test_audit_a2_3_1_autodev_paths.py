from __future__ import annotations

import ast
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.core.project_paths import (
    PROJECT_ROOT_ENV,
    default_project_path,
    default_project_root,
)


class AuditA231AutoDevPathsTests(unittest.TestCase):

    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parents[1]

    def test_default_root_uses_forward_slashes(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict(
                os.environ,
                {
                    PROJECT_ROOT_ENV: temp,
                },
            ):
                value = default_project_root()

        self.assertNotIn(
            "\\",
            value,
        )
        self.assertTrue(
            Path(value).is_absolute()
        )

    def test_default_project_path_joins_inside_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            with patch.dict(
                os.environ,
                {
                    PROJECT_ROOT_ENV: temp,
                },
            ):
                value = default_project_path(
                    "data",
                    "autodev",
                )

        expected = str(
            Path(temp).resolve()
            / "data/autodev"
        ).replace(
            "\\",
            "/",
        )

        self.assertEqual(
            value,
            expected,
        )

    def test_autodev_and_code_have_no_fixed_root_literal(self) -> None:
        offenders: list[str] = []

        for folder in (
            "app/autodev",
            "app/code",
        ):
            for path in (
                self.project_root / folder
            ).rglob("*.py"):
                source = path.read_text(
                    encoding="utf-8"
                )

                if (
                    "C:/JarvisAI" in source
                    or "C:\\\\JarvisAI" in source
                ):
                    offenders.append(
                        str(
                            path.relative_to(
                                self.project_root
                            )
                        )
                    )

        self.assertEqual(
            offenders,
            [],
        )

    def test_all_migrated_files_parse(self) -> None:
        errors: list[str] = []

        for folder in (
            "app/autodev",
            "app/code",
        ):
            for path in (
                self.project_root / folder
            ).rglob("*.py"):
                try:
                    source = path.read_text(
                        encoding="utf-8"
                    )
                    ast.parse(
                        source,
                        filename=str(
                            path.relative_to(
                                self.project_root
                            )
                        ),
                    )
                except Exception as error:
                    errors.append(
                        f"{path}: {error}"
                    )

        self.assertEqual(
            errors,
            [],
            "\n".join(errors),
        )

    def test_default_root_respects_environment(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            expected = str(
                Path(temp).resolve()
            ).replace(
                "\\",
                "/",
            )

            with patch.dict(
                os.environ,
                {
                    PROJECT_ROOT_ENV: temp,
                },
            ):
                actual = default_project_root()

        self.assertEqual(
            actual,
            expected,
        )


if __name__ == "__main__":
    unittest.main()
