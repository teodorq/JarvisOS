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
from app.gui.command_safety import is_read_only_learning_command


class B87B88BusinessReleaseIntegrationTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        for relative, content in {
            "main.py": "pass\n",
            "requirements.txt": "\n",
            "start_jarvis.bat": "@echo off\n",
            "start_jarvis.vbs": "Option Explicit\n",
            "app/gui/main_window.py": "class MainWindow: pass\n",
            "app/business/business_edition_service.py": "class BusinessEditionService: pass\n",
            "tests/test_sample.py": "# sample\n",
            "config/business_edition.json": "{}\n",
            "JARVIS_OS.ico": "icon",
            "JARVIS_OS.png": "png",
        }.items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        self.service = BusinessEditionService(self.root)
        self.suite = MagicMock()
        self.suite.business_edition = self.service
        self.router = SoftwareEngineerAutonomyOperationsRouter()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_combined_status_contains_b87_and_b88(self) -> None:
        result = self.service.business_release_status()
        self.assertEqual(result["stage"], "B87-B88")
        self.assertIn("installation", result)
        self.assertIn("release_candidate", result)

    def test_router_dispatches_b87_and_b88_status(self) -> None:
        b87 = self.router.try_handle(
            self.suite,
            command="Pokaż status instalatora Business Edition",
        )
        b88 = self.router.try_handle(
            self.suite,
            command="Pokaż status Release Candidate RC1",
        )
        combined = self.router.try_handle(
            self.suite,
            command="Pokaż status B87-B88",
        )
        self.assertEqual(b87["stage"], "B87")
        self.assertEqual(b88["stage"], "B88")
        self.assertEqual(combined["stage"], "B87-B88")

    def test_mutating_operations_are_confirmation_gated(self) -> None:
        for phrase in (
            "inicjalizuj pierwsze uruchomienie business edition",
            "eksportuj instalator business edition",
            "eksportuj bezpieczny deinstalator",
            "eksportuj release candidate rc1",
        ):
            self.assertIn(phrase, self.router.MUTATING_PHRASES)
            self.assertFalse(is_read_only_learning_command(phrase))

    def test_read_only_status_and_verification_are_safe(self) -> None:
        for phrase in (
            "pokaż status instalatora business edition",
            "pokaż status release candidate rc1",
            "zweryfikuj release candidate rc1",
            "pokaż status b87-b88",
        ):
            self.assertTrue(is_read_only_learning_command(phrase))

    def test_formatter_exposes_installation_and_release_gates(self) -> None:
        b87 = format_autonomy_operations_response(
            self.service.installation_manager_status()
        )
        b88 = format_autonomy_operations_response(
            self.service.release_candidate_status()
        )
        combined = format_autonomy_operations_response(
            self.service.business_release_status()
        )
        self.assertIn("Instalator:", b87)
        self.assertIn("bramki", b88)
        self.assertIn("B87 instalator", combined)


if __name__ == "__main__":
    unittest.main()
