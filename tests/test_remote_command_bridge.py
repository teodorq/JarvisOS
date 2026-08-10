from __future__ import annotations

import json
import threading
import unittest
import urllib.error
import urllib.request

from app.cloud.client import CloudPlannerClient, CloudPlannerSettings
from cloud_service.main import ServiceConfig, build_server
from cloud_service.remote_store import MemoryRemoteCommandStore

class RemoteCommandBridgeTests(unittest.TestCase):
    desktop_token = "desktop-token-with-enough-entropy"
    phone_token = "phone-token-with-enough-entropy"
    device_id = "desktop-main"

    def setUp(self) -> None:
        self.store = MemoryRemoteCommandStore()
        self.server = build_server(
            "127.0.0.1",
            0,
            config=ServiceConfig(
                api_token=self.desktop_token,
                phone_api_token=self.phone_token,
                environment="test",
            ),
            remote_store=self.store,
        )
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def _phone_request(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: dict | None = None,
        token: str | None = None,
    ) -> tuple[int, dict]:
        data = None
        headers = {
            "Accept": "application/json",
            "Authorization": f"Bearer {token or self.phone_token}",
        }
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(
            self.base_url + path, data=data, headers=headers, method=method
        )
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read().decode("utf-8"))

    def test_phone_page_is_public_but_contains_no_tokens(self) -> None:
        with urllib.request.urlopen(self.base_url + "/phone", timeout=2) as response:
            page = response.read().decode("utf-8")
            self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertIn("JARVIS OS", page)
        self.assertIn("sessionStorage", page)
        self.assertNotIn(self.desktop_token, page)
        self.assertNotIn(self.phone_token, page)
        self.assertNotIn("localStorage", page)

    def test_end_to_end_command_lifecycle(self) -> None:
        status, submitted = self._phone_request(
            "/v1/remote/commands",
            method="POST",
            payload={"device_id": self.device_id, "command": "status systemu"},
        )
        self.assertEqual(status, 202)
        self.assertEqual(submitted["status"], "queued")

        client = CloudPlannerClient(
            CloudPlannerSettings(
                base_url=self.base_url,
                api_token=self.desktop_token,
                timeout_seconds=2,
                remote_device_id=self.device_id,
            )
        )
        claimed = client.claim_remote_command()
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed["command"], "status systemu")
        self.assertIsNone(client.claim_remote_command())

        waiting = client.report_remote_command(
            claimed["id"],
            "waiting_local_confirmation",
            "Polecenie czeka na potwierdzenie na komputerze.",
        )
        self.assertEqual(waiting["status"], "waiting_local_confirmation")
        completed = client.report_remote_command(
            claimed["id"], "completed", "System dzia\u0142a poprawnie."
        )
        self.assertEqual(completed["status"], "completed")

        status, fetched = self._phone_request(
            f"/v1/remote/commands/{claimed['id']}?device_id={self.device_id}"
        )
        self.assertEqual(status, 200)
        self.assertEqual(fetched["message"], "System dzia\u0142a poprawnie.")

    def test_wrong_phone_token_is_rejected(self) -> None:
        status, payload = self._phone_request(
            "/v1/remote/commands",
            method="POST",
            payload={"device_id": self.device_id, "command": "status systemu"},
            token="wrong-token",
        )
        self.assertEqual(status, 401)
        self.assertEqual(payload["error"], "unauthorized")

    def test_sensitive_command_never_enters_the_queue(self) -> None:
        status, payload = self._phone_request(
            "/v1/remote/commands",
            method="POST",
            payload={
                "device_id": self.device_id,
                "command": "u\u017cyj token=super-secret-value",
            },
        )
        self.assertEqual(status, 422)
        self.assertEqual(payload["error"], "sensitive_command_requires_local")
        self.assertIsNone(self.store.claim_next(self.device_id))

    def test_health_reports_remote_bridge_without_exposing_tokens(self) -> None:
        with urllib.request.urlopen(self.base_url + "/health", timeout=2) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertTrue(payload["remote_configured"])
        serialized = json.dumps(payload)
        self.assertNotIn(self.desktop_token, serialized)
        self.assertNotIn(self.phone_token, serialized)

if __name__ == "__main__":
    unittest.main()
