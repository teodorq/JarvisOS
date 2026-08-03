from tempfile import TemporaryDirectory
import unittest

from app.stability.recovery_center import RuntimeRecoveryCenter


class B113RecoveryCenterTests(unittest.TestCase):
    def test_stale_heartbeat_creates_one_incident(self) -> None:
        with TemporaryDirectory() as temporary:
            center = RuntimeRecoveryCenter(temporary, stale_seconds=10)
            center.simulate_stale("voice")
            self.assertEqual(len(center.check()), 1)
            self.assertEqual(len(center.check()), 0)
            self.assertEqual(center.status()["open_incident_count"], 1)

    def test_recovery_closes_incident_and_restores_heartbeat(self) -> None:
        with TemporaryDirectory() as temporary:
            center = RuntimeRecoveryCenter(temporary, stale_seconds=10)
            center.simulate_stale("voice")
            center.check()
            result = center.recover()
            self.assertEqual(result["status"], "RECOVERED")
            self.assertEqual(center.status()["open_incident_count"], 0)
            self.assertEqual(center.status()["recovery_count"], 1)

    def test_recovery_without_incident_is_blocked(self) -> None:
        with TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "brak otwartego incydentu"):
                RuntimeRecoveryCenter(temporary).recover()


if __name__ == "__main__":
    unittest.main()
