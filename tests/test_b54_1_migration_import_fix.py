from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import json
import os
import shutil
import subprocess
import sys
import textwrap
import unittest


class B541MigrationImportFixTests(unittest.TestCase):

    def test_direct_script_execution_finds_project_app(
        self,
    ) -> None:
        project_root = Path(__file__).resolve().parents[1]
        source_script = (
            project_root
            / "tools"
            / "migrate_b54_diagnostics.py"
        )

        with TemporaryDirectory() as directory:
            root = Path(directory)
            tool_dir = root / "tools"
            package_dir = (
                root
                / "app"
                / "ai"
                / "software_engineer"
            )
            tool_dir.mkdir(parents=True)
            package_dir.mkdir(parents=True)

            shutil.copy2(
                source_script,
                tool_dir / source_script.name,
            )

            for init_path in (
                root / "app" / "__init__.py",
                root / "app" / "ai" / "__init__.py",
                package_dir / "__init__.py",
            ):
                init_path.parent.mkdir(
                    parents=True,
                    exist_ok=True,
                )
                init_path.write_text(
                    "",
                    encoding="utf-8",
                )

            (
                package_dir
                / "long_running_autonomy_store.py"
            ).write_text(
                textwrap.dedent(
                    """
                    from pathlib import Path

                    class LongRunningAutonomyStore:
                        def __init__(self, root):
                            self.path = (
                                Path(root)
                                / "data"
                                / "long_running.json"
                            )

                        def list_jobs(self, limit=5000):
                            return []

                        def compact(self):
                            return None
                    """
                ).lstrip(),
                encoding="utf-8",
            )

            (
                package_dir
                / "autonomous_diagnostics_service.py"
            ).write_text(
                textwrap.dedent(
                    """
                    from pathlib import Path
                    from types import SimpleNamespace

                    class AutonomousDiagnosticsService:
                        def __init__(
                            self,
                            root,
                            long_running_store=None,
                        ):
                            self.store = SimpleNamespace(
                                path=(
                                    Path(root)
                                    / "data"
                                    / "diagnostics.json"
                                )
                            )
                    """
                ).lstrip(),
                encoding="utf-8",
            )

            environment = dict(os.environ)
            environment.pop("PYTHONPATH", None)

            result = subprocess.run(
                [
                    sys.executable,
                    "tools/migrate_b54_diagnostics.py",
                ],
                cwd=root,
                env=environment,
                capture_output=True,
                text=True,
                timeout=30,
            )

        self.assertEqual(
            result.returncode,
            0,
            result.stdout + result.stderr,
        )
        payload = json.loads(result.stdout)
        self.assertTrue(payload["success"])
        self.assertEqual(
            payload["status"],
            "B54_DIAGNOSTICS_MIGRATION_COMPLETED",
        )


if __name__ == "__main__":
    unittest.main()
