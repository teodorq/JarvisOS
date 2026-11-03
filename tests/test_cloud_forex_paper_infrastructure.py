from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class CloudForexPaperInfrastructureTests(unittest.TestCase):
    def test_job_is_scheduled_scaled_down_and_paper_only(self) -> None:
        bicep = (ROOT / "infra" / "azure" / "paper-job.bicep").read_text(
            encoding="utf-8"
        )
        self.assertIn("resource paperJob 'Microsoft.App/jobs@2024-03-01'", bicep)
        self.assertIn("cronExpression: '2 * * * *'", bicep)
        self.assertIn("parallelism: 1", bicep)
        self.assertIn("replicaCompletionCount: 1", bicep)
        self.assertIn("JARVIS_OS_FOREX_PRIMARY_PROVIDER", bicep)
        self.assertIn("value: 'TWELVE_DATA_CLOUD'", bicep)
        self.assertIn("JARVIS_OS_FOREX_BASE_NEW_ENTRIES_ENABLED", bicep)
        self.assertIn("JARVIS_OS_FOREX_V3_SHADOW_SIMULATION_ENABLED", bicep)
        self.assertIn("JARVIS_OS_FOREX_V3_SHADOW_REVIEW_FINGERPRINT", bicep)
        self.assertNotIn("OANDA_PRACTICE_TOKEN", bicep)

    def test_state_is_private_and_uses_managed_identity(self) -> None:
        paper = (ROOT / "infra" / "azure" / "paper-job.bicep").read_text(
            encoding="utf-8"
        )
        main = (ROOT / "infra" / "azure" / "main.bicep").read_text(
            encoding="utf-8"
        )
        self.assertIn("name: 'forex-paper'", paper)
        self.assertIn("name: 'forex-paper-status'", paper)
        self.assertIn("publicAccess: 'None'", paper)
        self.assertIn("ba92f5b4-2d11-453d-a403-e96b0029c9fe", paper)
        self.assertIn("2a2b9908-6ea1-4ae2-8e65-a410df84e7d1", paper)
        self.assertIn("principalId: paperJob.identity.principalId", paper)
        self.assertIn("principalId: plannerPrincipalId", paper)
        self.assertIn("scope: paperStatusContainer", paper)
        self.assertIn("JARVIS_OS_FOREX_STATUS_CONTAINER", paper + main)
        self.assertIn("allowSharedKeyAccess: false", main)
        self.assertNotIn("FOREX_CLOUD_STORAGE_CONNECTION", paper + main)

    def test_market_keys_are_secure_deployment_parameters(self) -> None:
        main = (ROOT / "infra" / "azure" / "main.bicep").read_text(
            encoding="utf-8"
        )
        subscription = (
            ROOT / "infra" / "azure" / "subscription.bicep"
        ).read_text(encoding="utf-8")
        for source in (main, subscription):
            self.assertRegex(
                source,
                r"@secure\(\)\s+@description\([^\n]+\)\s+param "
                r"twelveDataApiKey string",
            )
            self.assertRegex(
                source,
                r"@secure\(\)\s+@description\([^\n]+\)\s+param "
                r"fmpApiKey string",
            )

    def test_standalone_deployer_passes_planner_identity(self) -> None:
        script = (
            ROOT / "tools" / "deploy_cloud_forex_paper.ps1"
        ).read_text(encoding="utf-8")
        self.assertIn('--query "identity.principalId"', script)
        self.assertIn('"plannerPrincipalId=$PlannerPrincipalId"', script)
        self.assertIn('statusContainer -ne "forex-paper-status"', script)


if __name__ == "__main__":
    unittest.main()
