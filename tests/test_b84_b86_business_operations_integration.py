from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock

from app.business.business_edition_service import BusinessEditionService
from app.ai.software_engineer.software_engineer_autonomy_operations_router import (
    SoftwareEngineerAutonomyOperationsRouter,
)
from app.ai.software_engineer.software_engineer_autonomy_operations_formatter import (
    format_autonomy_operations_response,
)


class B84B86BusinessOperationsIntegrationTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "config").mkdir()
        (self.root / "app").mkdir()
        (self.root / "tests").mkdir()
        (self.root / "app" / "sample.py").write_text("VALUE=1\n", encoding="utf-8")
        (self.root / "tests" / "test_sample.py").write_text("# sample\n", encoding="utf-8")
        (self.root / "main.py").write_text("pass\n", encoding="utf-8")
        self.service = BusinessEditionService(self.root)
        self.suite = MagicMock()
        self.suite.business_edition = self.service
        self.router = SoftwareEngineerAutonomyOperationsRouter()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_combined_status_contains_all_stages(self) -> None:
        result = self.service.business_operations_status()
        self.assertEqual(result["stage"], "B84-B86")
        self.assertIn("audit", result)
        self.assertIn("disaster_recovery", result)
        self.assertIn("updates", result)

    def test_router_dispatches_b84_b85_b86(self) -> None:
        b84 = self.router.try_handle(self.suite, command="Pokaż status centrum audytu")
        b85 = self.router.try_handle(self.suite, command="Pokaż status disaster recovery")
        b86 = self.router.try_handle(self.suite, command="Pokaż status centrum aktualizacji")
        self.assertEqual(b84["stage"], "B84")
        self.assertEqual(b85["stage"], "B85")
        self.assertEqual(b86["stage"], "B86")

    def test_dangerous_operations_are_confirmation_gated(self) -> None:
        for phrase in (
            "eksportuj raport audytu",
            "utwórz checkpoint business edition",
            "przygotuj pakiet przywracania",
            "przygotuj aktualizację business edition",
            "eksportuj instalator aktualizacji",
        ):
            self.assertIn(phrase, self.router.MUTATING_PHRASES)

    def test_formatter_exposes_business_operation_counts(self) -> None:
        text = format_autonomy_operations_response(
            self.service.business_operations_status()
        )
        self.assertIn("Audyt:", text)
        self.assertIn("checkpointy", text)
        self.assertIn("pakiety aktualizacji", text)


if __name__ == "__main__":
    unittest.main()
