from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest


class B2101ReleaseGateAndSourceLimitsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = Path(__file__).resolve().parents[1]
        self.runner = self.root / "tools" / "safe_development_unittest_runner.py"

    def test_business_runtime_remains_below_legacy_limit(self) -> None:
        path = self.root / "app" / "gui" / "business_command_runtime.py"
        self.assertLess(len(path.read_text(encoding="utf-8").splitlines()), 180)

    def test_smart_task_loop_remains_below_legacy_limit(self) -> None:
        path = self.root / "app" / "jarvis_experience" / "smart_task_loop.py"
        self.assertLess(len(path.read_text(encoding="utf-8").splitlines()), 130)

    def _run_fixture(self, body: str) -> tuple[subprocess.CompletedProcess[str], dict]:
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary)
            tests = base / "tests"
            tests.mkdir()
            (tests / "test_fixture.py").write_text(
                textwrap.dedent(body), encoding="utf-8"
            )
            arguments = base / "arguments.txt"
            arguments.write_text(
                "discover\n-s\n" + str(tests) + "\n-p\ntest_*.py\n",
                encoding="utf-8",
            )
            result_path = base / "result.json"
            completed = subprocess.run(
                [
                    sys.executable,
                    str(self.runner),
                    "--args-file",
                    str(arguments),
                    "--result-file",
                    str(result_path),
                ],
                cwd=self.root,
                text=True,
                capture_output=True,
                timeout=30,
                check=False,
            )
            return completed, json.loads(result_path.read_text(encoding="utf-8"))

    def test_runner_writes_pass_result_for_success(self) -> None:
        completed, result = self._run_fixture(
            """
            import unittest

            class FixtureTests(unittest.TestCase):
                def test_ok(self):
                    self.assertTrue(True)
            """
        )
        self.assertEqual(completed.returncode, 0)
        self.assertEqual(result["status"], "PASSED")
        self.assertEqual(result["tests"], 1)
        self.assertEqual(result["failures"], 0)
        self.assertEqual(result["errors"], 0)

    def test_runner_writes_fail_result_and_nonzero_exit(self) -> None:
        completed, result = self._run_fixture(
            """
            import unittest

            class FixtureTests(unittest.TestCase):
                def test_failure(self):
                    self.assertEqual(1, 2)
            """
        )
        self.assertNotEqual(completed.returncode, 0)
        self.assertEqual(result["status"], "FAILED")
        self.assertEqual(result["tests"], 1)
        self.assertEqual(result["failures"], 1)

    def test_runner_contract_is_bounded_and_uses_result_file(self) -> None:
        source = self.runner.read_text(encoding="utf-8")
        self.assertLess(len(source.splitlines()), 180)
        self.assertIn('"--result-file"', source)
        self.assertIn("_atomic_json", source)
        self.assertIn("result.wasSuccessful()", source)


if __name__ == "__main__":
    unittest.main()
