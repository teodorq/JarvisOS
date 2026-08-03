from __future__ import annotations

import subprocess
import sys
import unittest


class AuditA232RuntimeWarningTests(unittest.TestCase):

    def test_runtime_migration_module_runs_without_warning(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                "-W",
                "error",
                "-m",
                "app.core.runtime_migration",
                "--help",
            ],
            capture_output=True,
            text=True,
        )

        self.assertEqual(
            result.returncode,
            0,
            result.stdout + result.stderr,
        )
        self.assertNotIn(
            "RuntimeWarning",
            result.stderr,
        )


if __name__ == "__main__":
    unittest.main()
