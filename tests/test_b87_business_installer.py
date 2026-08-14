from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from app.business.installation_manager import BusinessInstallationManager


class B87BusinessInstallerTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self._seed_project()
        self.manager = BusinessInstallationManager(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _seed_project(self) -> None:
        files = {
            "main.py": "pass\n",
            "requirements.txt": "\n",
            "start_jarvis.bat": "@echo off\n",
            "start_jarvis.vbs": "Option Explicit\n",
            "app/gui/main_window.py": "class MainWindow: pass\n",
            "app/business/business_edition_service.py": "class BusinessEditionService: pass\n",
            "app/sample.py": "VALUE = 1\n",
            "tests/test_sample.py": "# sample\n",
            "config/business_edition.json": "{}\n",
            "JARVIS_OS.ico": "icon",
            "JARVIS_OS.png": "png",
        }
        for relative, content in files.items():
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    def test_status_reports_installation_ready(self) -> None:
        status = self.manager.status()
        self.assertTrue(status["success"])
        self.assertTrue(status["installation_ready"])
        self.assertEqual(status["stage"], "B87")

    def test_first_run_is_idempotent_and_hardened(self) -> None:
        first = self.manager.initialize_first_run()
        second = self.manager.initialize_first_run()
        self.assertTrue(first["first_run"]["completed"])
        self.assertTrue(second["first_run"]["completed"])
        config = json.loads(
            (self.root / "config/business_edition.json").read_text(encoding="utf-8")
        )
        self.assertFalse(config["safety"]["auto_approve"])
        self.assertTrue(config["safety"]["require_confirmation"])
        self.assertEqual(config["safety"]["max_active_executions"], 1)

    def test_setup_package_contains_verified_payload_and_scripts(self) -> None:
        result = self.manager.export_setup_package()
        self.assertEqual(result["status"], "BUSINESS_SETUP_PACKAGE_EXPORTED")
        package = Path(result["setup_package"]["path"])
        self.assertTrue(package.is_file())
        with zipfile.ZipFile(package) as archive:
            self.assertIsNone(archive.testzip())
            names = set(archive.namelist())
            self.assertIn("INSTALL_JARVIS_OS_BUSINESS.cmd", names)
            self.assertIn("INSTALL_JARVIS_OS_BUSINESS.ps1", names)
            self.assertIn("UNINSTALL_JARVIS_OS_BUSINESS.ps1", names)
            manifest = json.loads(
                archive.read("JARVIS_BUSINESS_SETUP_MANIFEST.json").decode("utf-8")
            )
            self.assertEqual(manifest["type"], "JARVIS_BUSINESS_SETUP")
            self.assertIn("main.py", manifest["files"])
            self.assertNotIn("data/business/installation_manager.json", manifest["files"])
            start = archive.read("PAYLOAD/start_jarvis.bat").decode("ascii")
            self.assertIn('%~dp0', start)
            self.assertNotIn("C:\\JarvisAI", start)
            hidden = archive.read("PAYLOAD/start_jarvis.vbs").decode("ascii")
            self.assertIn("shell.Run command, 0, False", hidden)

    def test_package_excludes_runtime_and_secret_like_artifacts(self) -> None:
        runtime = self.root / "AI_PLIKI/private.txt"
        runtime.parent.mkdir(parents=True)
        runtime.write_text("secret", encoding="utf-8")
        cache = self.root / "app/__pycache__/sample.pyc"
        cache.parent.mkdir(parents=True)
        cache.write_bytes(b"cache")
        package = Path(self.manager.export_setup_package()["setup_package"]["path"])
        with zipfile.ZipFile(package) as archive:
            names = set(archive.namelist())
        self.assertNotIn("PAYLOAD/AI_PLIKI/private.txt", names)
        self.assertNotIn("PAYLOAD/app/__pycache__/sample.pyc", names)

    def test_uninstaller_requires_explicit_word_and_backup(self) -> None:
        result = self.manager.export_uninstaller()
        cmd = Path(result["uninstaller_cmd"]).read_text(encoding="utf-8")
        ps1 = Path(result["uninstaller_script"]).read_text(encoding="utf-8-sig")
        self.assertIn("Wpisz USUN", cmd)
        self.assertIn("JARVIS_OS_BUSINESS_USER_DATA", ps1)
        self.assertIn("data\\business", ps1)

    def test_missing_required_file_blocks_export(self) -> None:
        (self.root / "main.py").unlink()
        result = self.manager.export_setup_package()
        self.assertFalse(result["success"])
        self.assertEqual(result["status"], "INSTALLATION_NOT_READY")


if __name__ == "__main__":
    unittest.main()
