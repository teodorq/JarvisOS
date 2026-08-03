from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from app.business.update_center import BusinessUpdateCenter


class B86BusinessUpdateCenterTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.center = BusinessUpdateCenter(self.root)
        self.center.inbox.mkdir(parents=True)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _package(
        self,
        name: str = "update.zip",
        *,
        relative: str = "app/example.py",
        data: bytes = b"VALUE = 2\n",
        expected: str | None = None,
    ) -> Path:
        target = self.center.inbox / name
        digest = expected or hashlib.sha256(data).hexdigest()
        manifest = {
            "schema_version": 1,
            "type": "JARVIS_BUSINESS_UPDATE",
            "update_id": "update-test-001",
            "version": "B86.TEST",
            "files": {relative: digest},
        }
        with zipfile.ZipFile(target, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr("JARVIS_UPDATE_MANIFEST.json", json.dumps(manifest))
            archive.writestr("PAYLOAD/" + relative, data)
        return target

    def test_scan_accepts_valid_hash_manifest(self) -> None:
        self._package()
        result = self.center.scan()
        self.assertEqual(result["valid_package_count"], 1)
        self.assertEqual(result["decision"], "VALID_PACKAGES")

    def test_stage_and_export_installer(self) -> None:
        self._package()
        staged = self.center.stage_latest()
        self.assertTrue(staged["success"])
        staging = Path(staged["staged_update"]["staging_path"])
        self.assertTrue((staging / "app" / "example.py").is_file())
        exported = self.center.export_installer()
        self.assertEqual(exported["decision"], "PREVIEW_READY")
        self.assertTrue(Path(exported["installer_cmd"]).is_file())
        script = Path(exported["installer_script"]).read_text(encoding="utf-8-sig")
        self.assertIn("update_backups", script)
        self.assertIn("python -m unittest discover", script)
        self.assertIn("NEW_FILES.txt", script)
        self.assertIn("Get-FileHash", script)
        self.assertIn("Remove-Item -LiteralPath $target", script)

    def test_bad_hash_is_rejected(self) -> None:
        self._package(expected="0" * 64)
        result = self.center.scan()
        self.assertEqual(result["valid_package_count"], 0)
        self.assertFalse(result["packages"][0]["valid"])

    def test_traversal_path_is_rejected(self) -> None:
        self._package(relative="../escape.py")
        result = self.center.scan()
        self.assertEqual(result["valid_package_count"], 0)
        self.assertIn("Niebezpieczna ścieżka", result["packages"][0]["errors"][0])


if __name__ == "__main__":
    unittest.main()
