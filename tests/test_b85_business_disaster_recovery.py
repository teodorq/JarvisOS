from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from app.business.disaster_recovery import BusinessDisasterRecovery


class B85BusinessDisasterRecoveryTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        (self.root / "app").mkdir()
        (self.root / "tests").mkdir()
        (self.root / "config").mkdir()
        (self.root / "app" / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
        (self.root / "tests" / "test_module.py").write_text("# test\n", encoding="utf-8")
        (self.root / "config" / "settings.json").write_text("{}", encoding="utf-8")
        (self.root / "main.py").write_text("print('ok')\n", encoding="utf-8")
        self.recovery = BusinessDisasterRecovery(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_create_and_verify_checkpoint(self) -> None:
        created = self.recovery.create_checkpoint()
        self.assertTrue(created["success"])
        checkpoint = Path(created["checkpoint"]["path"])
        self.assertTrue(checkpoint.is_file())
        verified = self.recovery.verify_latest()
        self.assertTrue(verified["success"])
        self.assertEqual(verified["verification"]["verification"], "VERIFIED")

    def test_manifest_contains_relative_safe_files(self) -> None:
        result = self.recovery.create_checkpoint()
        checkpoint = Path(result["checkpoint"]["path"])
        with zipfile.ZipFile(checkpoint) as archive:
            manifest = json.loads(
                archive.read("JARVIS_CHECKPOINT_MANIFEST.json").decode("utf-8")
            )
        self.assertIn("app/module.py", manifest["files"])
        self.assertNotIn("../app/module.py", manifest["files"])

    def test_tampered_checkpoint_is_rejected(self) -> None:
        result = self.recovery.create_checkpoint()
        checkpoint = Path(result["checkpoint"]["path"])
        with checkpoint.open("ab") as stream:
            stream.write(b"tamper")
        verified = self.recovery.verify_latest()
        self.assertFalse(verified["success"])
        self.assertEqual(verified["verification"]["verification"], "FAILED")

    def test_restore_package_is_offline_and_explicit(self) -> None:
        self.recovery.create_checkpoint()
        result = self.recovery.export_restore_package()
        self.assertEqual(result["decision"], "PREVIEW_READY")
        self.assertTrue(Path(result["restore_cmd"]).is_file())
        self.assertTrue(Path(result["restore_script"]).is_file())
        script = Path(result["restore_script"]).read_text(encoding="utf-8-sig")
        self.assertIn("python -m unittest discover", script)
        self.assertIn("disaster_restore_backups", script)
        self.assertIn("NEW_FILES.txt", script)
        self.assertIn("Get-FileHash", script)
        self.assertIn("Remove-Item -LiteralPath $target", script)


if __name__ == "__main__":
    unittest.main()
