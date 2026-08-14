import unittest
from pathlib import Path


class CloudOperationsWorkflowTests(unittest.TestCase):
    def test_daily_monitor_checks_the_real_relay(self) -> None:
        workflow = Path(
            ".github/workflows/cloud-health-monitor.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("schedule:", workflow)
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("jarvis-os-planner", workflow)
        self.assertIn(
            "extension.use_dynamic_install=yes_without_prompt", workflow
        )
        self.assertIn(
            'data.get("remote_access_verified") is True', workflow
        )
        self.assertIn(
            'data.get("remote_transport") == "azure_queue"', workflow
        )

    def test_rollback_is_manual_serialized_and_immutable(self) -> None:
        workflow = Path(
            ".github/workflows/cloud-rollback.yml"
        ).read_text(encoding="utf-8")
        self.assertIn("workflow_dispatch:", workflow)
        self.assertIn("image_sha:", workflow)
        self.assertIn("^[a-f0-9]{40}$", workflow)
        self.assertIn("jarvis-os-cloud-production", workflow)
        self.assertIn("jarvis-os-cloud:sha-${TARGET_SHA}", workflow)
        self.assertIn("JARVIS_OS_BUILD_SHA=${TARGET_SHA}", workflow)
        self.assertIn('data.get("build_sha") == sys.argv[2]', workflow)
        self.assertIn(
            'data.get("remote_access_verified") is True', workflow
        )
        self.assertNotIn(":latest", workflow)

    def test_deploy_and_rollback_share_the_production_lock(self) -> None:
        deploy = Path(".github/workflows/cloud-image.yml").read_text(
            encoding="utf-8"
        )
        rollback = Path(".github/workflows/cloud-rollback.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn("jarvis-os-cloud-production", deploy)
        self.assertIn("cancel-in-progress: false", deploy)
        self.assertIn("jarvis-os-cloud-production", rollback)
        self.assertIn("cancel-in-progress: false", rollback)
