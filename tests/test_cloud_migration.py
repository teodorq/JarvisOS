from __future__ import annotations

import json
import threading
import unittest
import urllib.request
from pathlib import Path
from unittest.mock import patch

from app.cloud.client import (
    CloudPlannerClient,
    CloudPlannerSettings,
    CloudPlannerUnavailable,
)
from app.cloud.contracts import CloudContractError, validate_cloud_plan
from app.cloud.hybrid_planner import HybridPlanner
from app.ai.commands.system_commands import SystemCommand
from app.ai.system_state import SystemState
from cloud_service.main import ServiceConfig, build_server


class _LocalPlanner:
    def __init__(self) -> None:
        self.calls = 0

    def create_plan(self, command: str) -> dict:
        self.calls += 1
        return {
            "goal": "local",
            "steps": [],
            "execute": False,
            "actions": [],
        }

    def detect_handler(self, command: str) -> str:
        return "standard"


class _FailingCloudClient:
    is_configured = True

    def create_plan(self, command: str) -> dict:
        raise CloudPlannerUnavailable("offline")


class _HealthyCloudClient:
    is_configured = True

    def health(self) -> dict:
        return {"status": "ok", "service": "jarvis-os-cloud-planner"}


class _OfflineCloudClient:
    is_configured = True

    def health(self) -> dict:
        raise CloudPlannerUnavailable("offline")

class CloudMigrationTests(unittest.TestCase):
    token = "test-token-with-enough-entropy"
    build_sha = "a" * 40

    def setUp(self) -> None:
        self.server = build_server(
            "127.0.0.1",
            0,
            config=ServiceConfig(
                api_token=self.token,
                environment="test",
                build_sha=self.build_sha,
            ),
        )
        self.thread = threading.Thread(
            target=self.server.serve_forever,
            daemon=True,
        )
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def test_health_does_not_require_or_expose_token(self) -> None:
        with urllib.request.urlopen(f"{self.base_url}/health", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["build_sha"], self.build_sha)
        self.assertTrue(payload["auth_configured"])
        self.assertNotIn(self.token, json.dumps(payload))

    def test_build_sha_comes_from_the_deployment_environment(self) -> None:
        with patch.dict(
            "os.environ",
            {"JARVIS_OS_BUILD_SHA": "B" * 40},
            clear=True,
        ):
            config = ServiceConfig.from_environment()
        self.assertEqual(config.build_sha, "b" * 40)

    def test_workflow_attests_revision_and_smokes_public_routes(self) -> None:
        workflow = Path(".github/workflows/cloud-image.yml").read_text(
            encoding="utf-8"
        )
        self.assertIn(
            'JARVIS_OS_BUILD_SHA=${{ github.sha }}', workflow
        )
        self.assertIn(
            'data.get("build_sha") == sys.argv[2]', workflow
        )
        self.assertIn('data.get("remote_access_verified") is True', workflow)
        for path in (
            "/mobile-start",
            "/mobile-logout",
            "/mobile-diagnostics",
            "/phone",
            "/phone.webmanifest",
        ):
            self.assertIn(path, workflow)
        self.assertIn("/.auth/login/aad", workflow)

    def test_authorized_client_receives_safe_plan(self) -> None:
        client = CloudPlannerClient(
            CloudPlannerSettings(
                base_url=self.base_url,
                api_token=self.token,
                timeout_seconds=2,
            )
        )
        plan = client.create_plan("status systemu")
        self.assertTrue(plan["execute"])
        self.assertEqual(plan["actions"][0]["action_type"], "SYSTEM_STATUS")

    def test_wrong_token_is_rejected(self) -> None:
        client = CloudPlannerClient(
            CloudPlannerSettings(
                base_url=self.base_url,
                api_token="wrong-token",
                timeout_seconds=2,
            )
        )
        with self.assertRaises(CloudPlannerUnavailable):
            client.create_plan("status systemu")

    def test_contract_rejects_write_action(self) -> None:
        with self.assertRaises(CloudContractError):
            validate_cloud_plan(
                {
                    "goal": "write",
                    "steps": ["create folder"],
                    "execute": True,
                    "handler_hint": "standard",
                    "actions": [
                        {
                            "action_type": "FOLDER_CREATE",
                            "target": "C:/unsafe",
                            "text": "",
                            "url": "",
                            "query": "",
                        }
                    ],
                }
            )

    def test_hybrid_planner_falls_back_without_breaking_desktop(self) -> None:
        local = _LocalPlanner()
        planner = HybridPlanner(
            local_planner=local,
            cloud_client=_FailingCloudClient(),
        )
        plan = planner.create_plan("anything")
        self.assertEqual(plan["goal"], "local")
        self.assertEqual(local.calls, 1)
        self.assertEqual(planner.status()["last_backend"], "local")


    def test_system_status_reports_azure_without_technical_booleans(self) -> None:
        summary = SystemState(cloud_client=_HealthyCloudClient()).summary()
        self.assertIn("JARVIS OS — status", summary)
        self.assertIn("Planer: Azure — połączony", summary)
        self.assertNotIn("SystemState", summary)
        self.assertNotIn("True", summary)

    def test_system_status_reports_safe_local_fallback(self) -> None:
        summary = SystemState(cloud_client=_OfflineCloudClient()).summary()
        self.assertIn("lokalny — bezpieczny fallback", summary)
        self.assertIn("Tryb awaryjny: gotowy", summary)

    def test_system_status_uses_live_voice_state(self) -> None:
        state = SystemState(
            cloud_client=_HealthyCloudClient(),
            voice_status_probe=lambda: True,
        )
        self.assertTrue(state.as_dict()["voice"])

    def test_cloud_status_command_uses_safe_system_action(self) -> None:
        action = SystemCommand().parse("status chmury")
        self.assertIsNotNone(action)
        self.assertEqual(action["action_type"], "SYSTEM_STATUS")

if __name__ == "__main__":
    unittest.main()
