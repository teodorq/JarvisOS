from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
import zipfile

from app.ai.software_engineer.autonomy_governance_store import AutonomyGovernanceStore
from app.ai.software_engineer.autonomous_release_service import AutonomousReleaseService
from tests.b62_b68_fakes import MemoryExecutionStore


class B66AutonomousReleaseTests(unittest.TestCase):
    def _service(self, directory, completed=1):
        root = Path(directory)
        (root / "app").mkdir(parents=True, exist_ok=True)
        (root / "tests").mkdir(parents=True, exist_ok=True)
        (root / "app" / "module.py").write_text("VALUE = 1\n", encoding="utf-8")
        (root / "tests" / "test_module.py").write_text("pass\n", encoding="utf-8")
        records = [
            {"execution_id": f"e{i}", "status": "COMPLETED"}
            for i in range(completed)
        ]
        return AutonomousReleaseService(
            root,
            store=AutonomyGovernanceStore(root),
            strategic_execution=SimpleNamespace(store=MemoryExecutionStore(records)),
        )

    def test_candidate_requires_completed_execution(self):
        with TemporaryDirectory() as directory:
            result = self._service(directory, completed=0).run_cycle()
            self.assertEqual(result["status"], "AUTONOMOUS_RELEASE_INSUFFICIENT_EVIDENCE")

    def test_candidate_creates_source_snapshot(self):
        with TemporaryDirectory() as directory:
            result = self._service(directory).run_cycle()
            release = result["release"]
            self.assertEqual(release["status"], "READY_FOR_APPROVAL")
            snapshot = Path(release["snapshot_path"])
            self.assertTrue(snapshot.is_file())
            with zipfile.ZipFile(snapshot) as archive:
                self.assertIn("app/module.py", archive.namelist())

    def test_same_manifest_does_not_create_second_candidate(self):
        with TemporaryDirectory() as directory:
            service = self._service(directory)
            service.run_cycle()
            result = service.run_cycle()
            self.assertEqual(result["status"], "AUTONOMOUS_RELEASE_NO_CHANGES")

    def test_activation_requires_explicit_call(self):
        with TemporaryDirectory() as directory:
            service = self._service(directory)
            candidate = service.run_cycle()["release"]
            self.assertEqual(service.status()["release"]["status"], "READY_FOR_APPROVAL")
            activated = service.activate(candidate["release_id"])
            self.assertEqual(activated["release"]["status"], "ACTIVE")

    def test_activation_unavailable_without_candidate(self):
        with TemporaryDirectory() as directory:
            service = self._service(directory)
            result = service.activate("missing")
            self.assertFalse(result["success"])

    def test_release_policy_never_auto_approves(self):
        with TemporaryDirectory() as directory:
            service = self._service(directory)
            result = service.update_policy({"auto_approve": True, "require_manual_activation": False})
            self.assertFalse(result["policy"]["auto_approve"])
            self.assertTrue(result["policy"]["require_manual_activation"])

    def test_manifest_changes_after_source_edit(self):
        with TemporaryDirectory() as directory:
            service = self._service(directory)
            first = service._manifest()["manifest_hash"]
            (Path(directory) / "app" / "module.py").write_text("VALUE = 2\n", encoding="utf-8")
            second = service._manifest()["manifest_hash"]
            self.assertNotEqual(first, second)

    def test_status_reports_b66(self):
        with TemporaryDirectory() as directory:
            self.assertEqual(self._service(directory).status()["stage"], "B66")


if __name__ == "__main__":
    unittest.main()
