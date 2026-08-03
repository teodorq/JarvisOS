from __future__ import annotations

from pathlib import Path
import tempfile
import unittest
from unittest.mock import MagicMock

from app.business.business_edition_service import BusinessEditionService
from app.ai.software_engineer.software_engineer_autonomy_operations_router import (
    SoftwareEngineerAutonomyOperationsRouter,
)


class B81B83BusinessPlatformIntegrationTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "config").mkdir()
        self.service = BusinessEditionService(self.root)
        self.suite = MagicMock()
        self.suite.business_edition = self.service
        self.router = SoftwareEngineerAutonomyOperationsRouter()

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_combined_status_contains_b81_b82_b83(self) -> None:
        status = self.service.business_platform_status()
        self.assertTrue(status["success"])
        self.assertEqual(status["stage"], "B81-B83")
        self.assertIn("organization_profiles", status)
        self.assertIn("license", status)
        self.assertIn("access_control", status)

    def test_router_dispatches_all_three_stages(self) -> None:
        b81 = self.router.try_handle(
            self.suite,
            command="Pokaż profile organizacji",
        )
        b82 = self.router.try_handle(
            self.suite,
            command="Pokaż status platformy licencyjnej",
        )
        b83 = self.router.try_handle(
            self.suite,
            command="Pokaż status ról i uprawnień",
        )
        self.assertEqual(b81["stage"], "B81")
        self.assertEqual(b82["stage"], "B82")
        self.assertEqual(b83["stage"], "B83")

    def test_mutating_business_commands_are_not_read_only(self) -> None:
        self.assertIn(
            "utwórz profil organizacji",
            self.router.MUTATING_PHRASES,
        )
        self.assertIn(
            "status profili organizacji",
            self.router.READ_PHRASES,
        )
