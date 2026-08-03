from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from app.business.access_control import BusinessAccessControl


class B83BusinessAccessControlTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.access = BusinessAccessControl(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_owner_has_full_permissions(self) -> None:
        result = self.access.authorize(
            "Aktywuj licencję business",
            read_only=False,
        )
        self.assertTrue(result["allowed"])
        self.assertEqual(result["role"], "OWNER")

    def test_auditor_is_read_only(self) -> None:
        self.access.set_active_role("AUDITOR")
        read = self.access.authorize("Pokaż status B83", read_only=True)
        write = self.access.authorize("Uruchom centrum", read_only=False)
        self.assertTrue(read["allowed"])
        self.assertFalse(write["allowed"])

    def test_operator_cannot_manage_license(self) -> None:
        self.access.set_active_role("OPERATOR")
        result = self.access.authorize(
            "Dezaktywuj licencję business",
            read_only=False,
        )
        self.assertFalse(result["allowed"])
        self.assertEqual(result["permission"], "license.manage")

    def test_audit_is_bounded(self) -> None:
        for index in range(230):
            self.access.authorize(f"status {index}", read_only=True)
        status = self.access.status()
        self.assertLessEqual(len(status["audit_events"]), 30)
