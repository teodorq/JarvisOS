from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.ai.software_engineer.autonomy_governance_store import AutonomyGovernanceStore
from app.ai.software_engineer.self_maintenance_service import SelfMaintenanceService


class B67SelfMaintenanceTests(unittest.TestCase):
    def _service(self, directory):
        return SelfMaintenanceService(
            directory,
            store=AutonomyGovernanceStore(directory),
        )

    def test_scan_finds_python_cache(self):
        with TemporaryDirectory() as directory:
            cache = Path(directory) / "app" / "__pycache__"
            cache.mkdir(parents=True)
            (cache / "x.pyc").write_bytes(b"cache")
            result = self._service(directory).scan()
            categories = {item["category"] for item in result["findings"]}
            self.assertIn("SAFE_CACHE_DIRECTORY", categories)

    def test_scan_finds_installer_leftover(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "APPLY_B99.cmd").write_text("echo test", encoding="utf-8")
            result = self._service(directory).scan()
            self.assertIn(
                "INSTALLER_COMMAND_LEFTOVER",
                {item["category"] for item in result["findings"]},
            )

    def test_scan_finds_syntax_error_without_deleting(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "app").mkdir()
            target = root / "app" / "broken.py"
            target.write_text("def broken(:\n", encoding="utf-8")
            result = self._service(directory).scan()
            self.assertIn("PYTHON_SYNTAX_ERROR", {item["category"] for item in result["findings"]})
            self.assertTrue(target.exists())

    def test_safe_cleanup_removes_only_safe_findings(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            cache = root / "app" / "__pycache__"
            cache.mkdir(parents=True)
            source = root / "app" / "source.py"
            source.write_text("VALUE = 1\n", encoding="utf-8")
            service = self._service(directory)
            service.scan()
            service.apply_safe_cleanup()
            self.assertFalse(cache.exists())
            self.assertTrue(source.exists())

    def test_auto_cleanup_cannot_be_enabled(self):
        with TemporaryDirectory() as directory:
            result = self._service(directory).update_policy({"auto_cleanup": True, "auto_approve": True})
            self.assertFalse(result["policy"]["auto_cleanup"])
            self.assertFalse(result["policy"]["auto_approve"])

    def test_archive_and_ai_files_are_excluded(self):
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "archive" / "__pycache__").mkdir(parents=True)
            (root / "AI_PLIKI" / "__pycache__").mkdir(parents=True)
            result = self._service(directory).scan()
            paths = {item["path"] for item in result["findings"]}
            self.assertFalse(any(path.startswith("archive/") for path in paths))
            self.assertFalse(any(path.startswith("AI_PLIKI/") for path in paths))

    def test_scan_records_history(self):
        with TemporaryDirectory() as directory:
            service = self._service(directory)
            service.scan()
            self.assertTrue(service.store.history(stage="B67", limit=10))

    def test_status_reports_b67(self):
        with TemporaryDirectory() as directory:
            self.assertEqual(self._service(directory).status()["stage"], "B67")


if __name__ == "__main__":
    unittest.main()
