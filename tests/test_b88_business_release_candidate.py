from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
import zipfile

from app.business.business_edition_service import BusinessEditionService


class B88BusinessReleaseCandidateTests(unittest.TestCase):

    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self._seed_project()
        self.service = BusinessEditionService(self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def _seed_project(self) -> None:
        files = {
            "main.py": "pass\n",
            "requirements.txt": "\n",
            "start_jarvis.bat": "@echo off\n",
            "install.bat": "@echo off\n",
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

    def _complete_gates(self) -> dict:
        self.service.release_candidate.record_validation({
            "b80_b88": "PASS",
            "b5x": "PASS",
            "full_project": "PASS",
            "gui_smoke": "PASS",
        })
        checkpoint = self.service.create_business_checkpoint()
        self.assertTrue(checkpoint["success"])
        self.service.create_integrity_manifest([
            "main.py",
            "app/sample.py",
            "app/gui/main_window.py",
            "app/business/business_edition_service.py",
        ])
        return self.service.release_candidate_status()

    def test_status_exposes_eight_bounded_gates(self) -> None:
        status = self.service.release_candidate_status()
        self.assertEqual(status["stage"], "B88")
        self.assertEqual(len(status["gates"]), 8)
        self.assertFalse(status["release_ready"])
        self.assertIn("checkpoint_verified", status["errors"])

    def test_all_gates_can_reach_rc_ready(self) -> None:
        status = self._complete_gates()
        self.assertTrue(status["release_ready"])
        self.assertEqual(status["decision"], "RC_READY")
        self.assertTrue(all(status["gates"].values()))

    def test_export_and_verify_release_candidate(self) -> None:
        self._complete_gates()
        exported = self.service.export_business_release_candidate()
        self.assertTrue(exported["success"])
        self.assertEqual(exported["status"], "BUSINESS_RELEASE_CANDIDATE_EXPORTED")
        package = Path(exported["release"]["path"])
        with zipfile.ZipFile(package) as archive:
            self.assertIsNone(archive.testzip())
            manifest = json.loads(
                archive.read("JARVIS_RC1_RELEASE_MANIFEST.json").decode("utf-8")
            )
            self.assertEqual(manifest["type"], "JARVIS_BUSINESS_RELEASE_CANDIDATE")
            self.assertTrue(all(manifest["gates"].values()))
            self.assertIn("RELEASE_NOTES_RC1.txt", archive.namelist())
        verified = self.service.verify_business_release_candidate()
        self.assertTrue(verified["success"])
        self.assertEqual(verified["verification"], "VERIFIED")

    def test_tampered_release_is_rejected(self) -> None:
        self._complete_gates()
        exported = self.service.export_business_release_candidate()
        package = Path(exported["release"]["path"])
        package.write_bytes(package.read_bytes() + b"tamper")
        verified = self.service.verify_business_release_candidate()
        self.assertFalse(verified["success"])
        self.assertIn("Niezgodny SHA-256", verified["errors"][0])

    def test_integrity_change_reopens_gate(self) -> None:
        self._complete_gates()
        (self.root / "app/sample.py").write_text("VALUE = 2\n", encoding="utf-8")
        status = self.service.release_candidate_status()
        self.assertFalse(status["gates"]["integrity_verified"])
        self.assertFalse(status["release_ready"])


if __name__ == "__main__":
    unittest.main()
