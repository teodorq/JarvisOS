from __future__ import annotations

from tempfile import TemporaryDirectory
import unittest

from app.intelligence.autonomy_center import AutonomyControlCenterV2


class B105AutonomyCenter2Tests(unittest.TestCase):

    def test_job_tracks_progress_and_releases_lease(self) -> None:
        with TemporaryDirectory() as temporary:
            service = AutonomyControlCenterV2(temporary)
            job = service.create_job("Demo", ["Krok 1", "Krok 2"])
            service.start(job["job_id"])
            first = service.advance("OK")
            self.assertEqual(first["status"], "RUNNING")
            completed = service.advance("OK")
            self.assertEqual(completed["status"], "COMPLETED")
            status = service.status()
            self.assertEqual(status["active_job"]["status"], "IDLE")
            self.assertEqual(status["lease"], {})

    def test_only_one_active_execution_is_allowed(self) -> None:
        with TemporaryDirectory() as temporary:
            service = AutonomyControlCenterV2(temporary)
            first = service.create_job("Pierwsze", ["A"])
            service.create_job("Drugie", ["B"])
            service.start(first["job_id"])
            with self.assertRaises(RuntimeError):
                service.start()

    def test_pause_resume_and_cancel_are_persistent(self) -> None:
        with TemporaryDirectory() as temporary:
            service = AutonomyControlCenterV2(temporary)
            service.create_job("Demo", ["A", "B"])
            service.start()
            self.assertEqual(service.pause()["status"], "PAUSED")
            self.assertEqual(service.resume()["status"], "RUNNING")
            self.assertEqual(service.cancel()["status"], "CANCELLED")
            self.assertEqual(AutonomyControlCenterV2(temporary).status()["active_job"]["status"], "IDLE")


if __name__ == "__main__":
    unittest.main()
