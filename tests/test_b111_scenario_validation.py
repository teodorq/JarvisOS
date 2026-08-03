from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from app.stability.scenario_validator import ScenarioValidationCenter


class B111ScenarioValidationTests(unittest.TestCase):
    def test_real_scenario_baseline_passes_with_required_layout(self) -> None:
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative in ("main.py", "app/ai/brain.py", "app/gui/main_window.py", "app/assistant/controller.py"):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# demo\n", encoding="utf-8")
            (root / "tests").mkdir()
            (root / "config").mkdir()
            (root / "config/business_integrity_manifest.json").write_text(
                json.dumps({"files": {"main.py": "abc"}}), encoding="utf-8"
            )
            runtime = {
                "conversation": {"status": "READY"},
                "intelligence": {"status": "READY"},
                "productivity": {"status": "READY"},
                "safety": {"auto_approve": False, "remote_code_execution": False},
            }
            result = ScenarioValidationCenter(root).run(runtime)
            self.assertEqual(result["status"], "PASSED")
            self.assertEqual(result["passed"], 5)

    def test_missing_layout_is_reported_without_exception(self) -> None:
        with TemporaryDirectory() as temporary:
            center = ScenarioValidationCenter(temporary)
            result = center.run({})
            self.assertEqual(result["status"], "FAILED")
            self.assertGreater(result["failed"], 0)

    def test_status_persists_latest_run(self) -> None:
        with TemporaryDirectory() as temporary:
            center = ScenarioValidationCenter(temporary)
            center.run({})
            status = center.status()
            self.assertEqual(status["run_count"], 1)
            self.assertEqual(status["latest_total"], 5)


if __name__ == "__main__":
    unittest.main()
