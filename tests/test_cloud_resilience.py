from __future__ import annotations

import json
import os
import threading
import unittest
import urllib.error
import urllib.request
from unittest.mock import patch

from app.cloud.client import (
    CloudPlannerClient,
    CloudPlannerSettings,
    CloudPlannerUnavailable,
)
from app.cloud.hybrid_planner import HybridPlanner
from cloud_service.main import ServiceConfig, build_server


class _Clock:
    def __init__(self) -> None:
        self.value = 100.0

    def __call__(self) -> float:
        return self.value

    def advance(self, seconds: float) -> None:
        self.value += seconds


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


class _FailOnceCloudClient:
    is_configured = True

    def __init__(self) -> None:
        self.calls = 0

    def create_plan(self, command: str) -> dict:
        self.calls += 1
        if self.calls == 1:
            raise CloudPlannerUnavailable("offline")
        return {
            "goal": "cloud",
            "steps": [],
            "execute": False,
            "actions": [],
        }


class CloudCircuitBreakerTests(unittest.TestCase):
    def test_failure_uses_local_planner_until_cooldown_expires(self) -> None:
        clock = _Clock()
        local = _LocalPlanner()
        cloud = _FailOnceCloudClient()
        planner = HybridPlanner(
            local_planner=local,
            cloud_client=cloud,
            failure_cooldown_seconds=60,
            clock=clock,
        )

        self.assertEqual(planner.create_plan("first")["goal"], "local")
        self.assertEqual(planner.create_plan("second")["goal"], "local")
        self.assertEqual(cloud.calls, 1)
        self.assertEqual(local.calls, 2)
        self.assertTrue(planner.status()["circuit_open"])
        self.assertEqual(planner.status()["retry_in_seconds"], 60.0)

        clock.advance(60)
        self.assertEqual(planner.create_plan("third")["goal"], "cloud")
        self.assertEqual(cloud.calls, 2)
        self.assertFalse(planner.status()["circuit_open"])
        self.assertEqual(planner.status()["last_backend"], "cloud")

    def test_new_cooldown_environment_name_is_used(self) -> None:
        with patch.dict(
            os.environ,
            {"JARVIS_OS_CLOUD_FAILURE_COOLDOWN_SECONDS": "12"},
            clear=True,
        ):
            planner = HybridPlanner(
                local_planner=_LocalPlanner(),
                cloud_client=_FailOnceCloudClient(),
            )
        self.assertEqual(planner.failure_cooldown_seconds, 12.0)


class CloudRateLimitTests(unittest.TestCase):
    token = "test-rate-limit-token"

    def setUp(self) -> None:
        self.server = build_server(
            "127.0.0.1",
            0,
            config=ServiceConfig(
                api_token=self.token,
                environment="test",
                requests_per_minute=1,
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

    def client(self, token: str) -> CloudPlannerClient:
        return CloudPlannerClient(
            CloudPlannerSettings(
                base_url=self.base_url,
                api_token=token,
                timeout_seconds=2,
            )
        )

    def test_only_authorized_plans_consume_the_rate_limit(self) -> None:
        with self.assertRaises(CloudPlannerUnavailable):
            self.client("wrong-token").create_plan("status systemu")

        plan = self.client(self.token).create_plan("status systemu")
        self.assertEqual(plan["actions"][0]["action_type"], "SYSTEM_STATUS")

        payload = json.dumps(
            {"schema_version": 1, "command": "status systemu"}
        ).encode("utf-8")
        request = urllib.request.Request(
            f"{self.base_url}/v1/plan",
            data=payload,
            headers={
                "Authorization": f"Bearer {self.token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with self.assertRaises(urllib.error.HTTPError) as context:
            urllib.request.urlopen(request, timeout=2)
        self.assertEqual(context.exception.code, 429)
        self.assertEqual(context.exception.headers["Retry-After"], "60")

        with urllib.request.urlopen(
            f"{self.base_url}/health", timeout=2
        ) as response:
            health = json.loads(response.read().decode("utf-8"))
        self.assertEqual(health["status"], "ok")

    def test_new_rate_limit_environment_name_is_bounded(self) -> None:
        values = {
            "JARVIS_OS_CLOUD_REQUESTS_PER_MINUTE": "500",
        }
        with patch.dict(os.environ, values, clear=True):
            config = ServiceConfig.from_environment()
        self.assertEqual(config.requests_per_minute, 120)


if __name__ == "__main__":
    unittest.main()
