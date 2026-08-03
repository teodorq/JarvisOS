from __future__ import annotations

import json
import threading
import unittest
import urllib.request

from app.cloud.client import (
    CloudPlannerClient,
    CloudPlannerSettings,
    CloudPlannerUnavailable,
)
from app.cloud.contracts import CloudContractError, validate_cloud_plan
from app.cloud.hybrid_planner import HybridPlanner
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


class CloudMigrationTests(unittest.TestCase):
    token = "test-token-with-enough-entropy"

    def setUp(self) -> None:
        self.server = build_server(
            "127.0.0.1",
            0,
            config=ServiceConfig(api_token=self.token, environment="test"),
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
        self.assertTrue(payload["auth_configured"])
        self.assertNotIn(self.token, json.dumps(payload))

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


if __name__ == "__main__":
    unittest.main()
