from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from app.stability.beta_readiness import BusinessBetaReadinessCenter


class B115BusinessBetaTests(unittest.TestCase):
    @staticmethod
    def passing_snapshot() -> dict:
        return {
            "scenario_status": "PASSED",
            "performance_score": 95,
            "open_incidents": 0,
            "restart_restored": True,
            "safe_defaults": True,
        }

    def test_beta_audit_requires_all_five_gates(self) -> None:
        with TemporaryDirectory() as temporary:
            center = BusinessBetaReadinessCenter(temporary)
            result = center.audit(self.passing_snapshot())
            self.assertEqual(result["status"], "PASSED")
            self.assertEqual(result["passed"], 5)

    def test_blocked_audit_cannot_be_confirmed(self) -> None:
        with TemporaryDirectory() as temporary:
            center = BusinessBetaReadinessCenter(temporary)
            center.audit({})
            with self.assertRaisesRegex(ValueError, "nie są jeszcze zaliczone"):
                center.confirm()

    def test_confirmation_exports_local_report_without_publication(self) -> None:
        with TemporaryDirectory() as temporary:
            center = BusinessBetaReadinessCenter(temporary)
            center.audit(self.passing_snapshot())
            confirmation = center.confirm()
            self.assertEqual(confirmation["status"], "BUSINESS_BETA_READY")
            self.assertFalse(confirmation["automatic_publication"])
            target = Path(temporary) / "AI_PLIKI/reports/JARVIS_BUSINESS_BETA_READINESS.json"
            self.assertTrue(target.is_file())


if __name__ == "__main__":
    unittest.main()
