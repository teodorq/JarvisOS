from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import tempfile
import unittest

from app.business.business_config import BusinessConfigStore
from app.business.business_license import BusinessLicenseManager


class B82BusinessLicensePlatformTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "config").mkdir()
        self.config = BusinessConfigStore(self.root).ensure()
        self.manager = BusinessLicenseManager(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_owner_mode_remains_active(self) -> None:
        status = self.manager.status(self.config)
        self.assertTrue(status["active"])
        self.assertEqual(status["status"], "OWNER_DEVELOPMENT")

    def test_trial_is_machine_bound_and_bounded(self) -> None:
        status = self.manager.start_trial(self.config, days=14)
        self.assertTrue(status["active"])
        self.assertEqual(status["status"], "TRIAL_ACTIVE")
        self.assertEqual(
            status["machine_fingerprint"],
            self.manager.machine_fingerprint(),
        )

    def test_valid_offline_package_activates(self) -> None:
        package = {
            "product_code": self.manager.PRODUCT_CODE,
            "license_id": "CUSTOMER-001",
            "organization": "Firma Test",
            "machine_fingerprint": self.manager.machine_fingerprint(),
            "expires_at": (
                datetime.now(timezone.utc) + timedelta(days=365)
            ).isoformat(),
        }
        package["activation_code"] = self.manager.activation_code(package)
        status = self.manager.activate_offline(package, self.config)
        self.assertTrue(status["active"])
        self.assertEqual(status["mode"], "OFFLINE_ACTIVE")

    def test_wrong_machine_is_rejected(self) -> None:
        package = {
            "product_code": self.manager.PRODUCT_CODE,
            "license_id": "CUSTOMER-002",
            "organization": "Firma Test",
            "machine_fingerprint": "WRONG-MACHINE",
            "expires_at": "",
        }
        package["activation_code"] = self.manager.activation_code(package)
        status = self.manager.activate_offline(package, self.config)
        self.assertFalse(status["active"])
        self.assertEqual(status["status"], "MACHINE_MISMATCH")
