from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest

from app.business.business_config import BusinessConfigStore
from app.business.organization_profiles import OrganizationProfileStore


class B81OrganizationProfileTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "config").mkdir()
        BusinessConfigStore(self.root).ensure()
        self.store = OrganizationProfileStore(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_default_profile_is_created(self) -> None:
        status = self.store.status()
        self.assertTrue(status["success"])
        self.assertEqual(status["stage"], "B81")
        self.assertEqual(status["profile_count"], 1)
        self.assertTrue(status["active_profile_id"])

    def test_snapshot_activation_and_export(self) -> None:
        created = self.store.snapshot_current("Klient testowy")
        profile_id = created["profile"]["profile_id"]
        self.assertEqual(created["decision"], "CREATED")

        activated = self.store.activate(profile_id)
        self.assertEqual(activated["decision"], "ACTIVATED")
        self.assertEqual(activated["active_profile_id"], profile_id)

        exported = self.store.export_active()
        target = Path(exported["export_path"])
        self.assertTrue(target.is_file())
        payload = json.loads(target.read_text(encoding="utf-8"))
        self.assertEqual(
            payload["type"],
            "JARVIS_BUSINESS_ORGANIZATION_PROFILE",
        )

    def test_import_gets_new_identity(self) -> None:
        original = self.store.snapshot_current("Import")
        package = {"profile": original["profile"]}
        imported = self.store.import_package(package)
        self.assertTrue(imported["success"])
        self.assertNotEqual(
            imported["profile"]["profile_id"],
            original["profile"]["profile_id"],
        )
