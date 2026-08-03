from pathlib import Path
from tempfile import TemporaryDirectory
import json
import unittest

from app.productivity.controller import ProductivitySuiteController


class B110DailyProductivityTests(unittest.TestCase):
    def test_report_aggregates_b106_b109_and_exports_two_formats(self) -> None:
        with TemporaryDirectory() as temporary:
            controller = ProductivitySuiteController(temporary)
            controller.handle("Utwórz szkic email demo")
            controller.handle("Oznacz szkic gotowy")
            controller.handle("Dodaj spotkanie demo")
            controller.handle("Utwórz dokument demo")
            controller.handle("Dodaj przypomnienie B109 demo")
            response = controller.handle("Generuj raport dnia B110")
            self.assertIn("raport zapisany", response)
            status = controller.reporting.status()
            latest = status["latest_report"]
            self.assertTrue(Path(latest["text_path"]).is_file())
            self.assertTrue(Path(latest["json_path"]).is_file())
            payload = json.loads(Path(latest["json_path"]).read_text(encoding="utf-8"))
            self.assertFalse(payload["remote_delivery"])
            self.assertGreaterEqual(len(payload["next_day_plan"]), 1)

    def test_status_before_export_is_ready(self) -> None:
        with TemporaryDirectory() as temporary:
            status = ProductivitySuiteController(temporary).reporting.status()
            self.assertEqual(status["status"], "DAILY_PRODUCTIVITY_REPORTING_READY")
            self.assertEqual(status["report_count"], 0)


if __name__ == "__main__":
    unittest.main()
