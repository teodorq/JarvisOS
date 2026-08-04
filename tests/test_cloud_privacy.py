from __future__ import annotations

import json
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from app.cloud.client import (
    CloudPlannerClient,
    CloudPlannerSettings,
    CloudSensitiveCommand,
)
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


class _PrivacyThenCloudClient:
    is_configured = True

    def __init__(self) -> None:
        self.calls = 0

    def create_plan(self, command: str) -> dict:
        self.calls += 1
        if self.calls == 1:
            raise CloudSensitiveCommand(
                "sensitive command requires local planning"
            )
        return {
            "goal": "cloud",
            "steps": [],
            "execute": False,
            "actions": [],
        }


class CloudPrivacyClientTests(unittest.TestCase):
    def test_sensitive_command_is_blocked_before_network_call(self) -> None:
        client = CloudPlannerClient(
            CloudPlannerSettings(
                base_url="https://cloud.example",
                api_token="configured-token",
            )
        )
        with patch("urllib.request.urlopen") as urlopen:
            with self.assertRaises(CloudSensitiveCommand):
                client.create_plan("sprawdź api_key=very-secret-value")
        urlopen.assert_not_called()

    def test_privacy_fallback_does_not_open_outage_circuit(self) -> None:
        local = _LocalPlanner()
        cloud = _PrivacyThenCloudClient()
        planner = HybridPlanner(local_planner=local, cloud_client=cloud)

        self.assertEqual(
            planner.create_plan("secret=hidden-value")["goal"],
            "local",
        )
        self.assertFalse(planner.status()["circuit_open"])
        self.assertEqual(
            planner.create_plan("status systemu")["goal"],
            "cloud",
        )
        self.assertEqual(cloud.calls, 2)


class CloudPrivacyServerTests(unittest.TestCase):
    token = "privacy-test-token"

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

    def test_server_rejects_sensitive_command_without_echoing_it(self) -> None:
        secret = "do-not-send-this-secret"
        request = urllib.request.Request(
            f"{self.base_url}/v1/plan",
            data=json.dumps(
                {
                    "schema_version": 1,
                    "command": f"status token={secret}",
                }
            ).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(request, timeout=2)
        self.assertEqual(context.exception.code, 422)
        payload = context.exception.read().decode("utf-8")
        self.assertIn("sensitive_command_requires_local", payload)
        self.assertNotIn(secret, payload)
