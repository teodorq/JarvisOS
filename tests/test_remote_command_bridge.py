from __future__ import annotations

import http.client
import json
import threading
import unittest
import urllib.error
import urllib.request

from app.cloud.client import (
    CloudPlannerClient,
    CloudPlannerSettings,
    CloudPlannerUnavailable,
)
from cloud_service.main import ServiceConfig, build_server
from cloud_service.remote_store import (
    AzureTableRemoteCommandStore,
    MemoryRemoteCommandStore,
    RemoteStoreConflict,
)


class FakeQueueMessage:
    def __init__(self, content: str) -> None:
        self.content = content
        self.id = "azure-message-id"
        self.pop_receipt = "azure-pop-receipt"


class FakeQueueClient:
    def __init__(self, records: list[dict] | None = None) -> None:
        self.messages = [
            FakeQueueMessage(json.dumps(record))
            for record in (records or [])
        ]
        self.delivered = False
        self.deleted: list[tuple[str, str]] = []
        self.receive_options: dict = {}

    def receive_messages(self, **options):
        self.receive_options = options
        if self.delivered or not self.messages:
            return []
        self.delivered = True
        return [self.messages[0]]

    def delete_message(self, message_id: str, pop_receipt: str) -> None:
        self.deleted.append((message_id, pop_receipt))
        self.messages.clear()


class FakeResourceExistsError(Exception):
    pass


class FakeAzureTable:
    def __init__(self) -> None:
        self.records: dict[tuple[str, str], dict] = {}

    def create_entity(self, entity: dict) -> None:
        key = (entity["PartitionKey"], entity["RowKey"])
        if key in self.records:
            raise FakeResourceExistsError
        self.records[key] = dict(entity)

    def get_entity(self, device_id: str, command_id: str) -> dict:
        return dict(self.records[(device_id, command_id)])

    def query_entities(self, **_options):
        return [dict(record) for record in self.records.values()]

    def delete_entity(self, device_id: str, command_id: str) -> None:
        self.records.pop((device_id, command_id), None)


class FakeAzureSendQueue:
    def __init__(self) -> None:
        self.sent: list[tuple[str, int]] = []

    def send_message(self, message: str, *, time_to_live: int) -> None:
        self.sent.append((message, time_to_live))


class RemoteCommandBridgeTests(unittest.TestCase):
    desktop_token = "desktop-token-with-enough-entropy"
    phone_token = "phone-token-with-enough-entropy"
    device_id = "desktop-main"
    queue_url = (
        "https://jarvis.queue.core.windows.net/commands"
        "?sv=2025-01-05&se=2030-01-01T00%3A00Z&sp=p&sig=test"
    )

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
        self.thread = threading.Thread(
            target=self.server.serve_forever, daemon=True
        )
        self.thread.start()
        host, port = self.server.server_address
        self.base_url = f"http://{host}:{port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def _settings(self, *, queue_url: str = "") -> CloudPlannerSettings:
        return CloudPlannerSettings(
            base_url=self.base_url,
            api_token=self.desktop_token,
            timeout_seconds=2,
            remote_device_id=self.device_id,
            remote_queue_url=queue_url,
        )

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
            self.base_url + path,
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with urllib.request.urlopen(request, timeout=2) as response:
                body = response.read()
                return response.status, json.loads(body.decode("utf-8"))
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read().decode("utf-8"))

    def test_phone_page_is_public_but_contains_no_tokens(self) -> None:
        with urllib.request.urlopen(
            self.base_url + "/phone", timeout=2
        ) as response:
            page = response.read().decode("utf-8")
            self.assertEqual(response.headers["X-Frame-Options"], "DENY")
        self.assertIn("JARVIS OS", page)
        self.assertIn("KOMPUTER ONLINE", page)
        self.assertIn("sessionStorage", page)
        self.assertIn("jarvisPendingRequest", page)
        self.assertIn("crypto.subtle.digest", page)
        self.assertIn("request_id", page)
        self.assertIn("phone.webmanifest", page)
        self.assertIn("beforeinstallprompt", page)
        self.assertIn("jarvisLastCommand", page)
        self.assertIn("/.auth/logout", page)
        self.assertNotIn("Kod parowania", page)
        self.assertNotIn(self.desktop_token, page)
        self.assertNotIn(self.phone_token, page)
        self.assertNotIn("localStorage", page)

    def test_phone_pwa_assets_are_public_and_scoped(self) -> None:
        with urllib.request.urlopen(
            self.base_url + "/phone.webmanifest", timeout=2
        ) as response:
            manifest = json.loads(response.read().decode("utf-8"))
            self.assertEqual(
                response.headers.get_content_type(),
                "application/manifest+json",
            )
        self.assertEqual(manifest["display"], "standalone")
        self.assertEqual(manifest["scope"], "/phone")
        with urllib.request.urlopen(
            self.base_url + "/phone-sw.js", timeout=2
        ) as response:
            service_worker = response.read().decode("utf-8")
            self.assertEqual(
                response.headers["Service-Worker-Allowed"], "/phone"
            )
        self.assertIn("phone-offline", service_worker)

    def test_end_to_end_command_lifecycle_with_http_fallback(self) -> None:
        status, submitted = self._phone_request(
            "/v1/remote/commands",
            method="POST",
            payload={
                "device_id": self.device_id,
                "command": "status systemu",
            },
        )
        self.assertEqual(status, 202)
        self.assertEqual(submitted["status"], "queued")
        self.assertEqual(submitted["kind"], "command")

        client = CloudPlannerClient(self._settings())
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
            claimed["id"], "completed", "System działa poprawnie."
        )
        self.assertEqual(completed["status"], "completed")

        status, fetched = self._phone_request(
            f"/v1/remote/commands/{claimed['id']}"
            f"?device_id={self.device_id}"
        )
        self.assertEqual(status, 200)
        self.assertEqual(fetched["message"], "System działa poprawnie.")

    def test_retry_with_same_request_id_creates_one_command(self) -> None:
        request_id = "a" * 32
        payload = {
            "device_id": self.device_id,
            "command": "status systemu",
            "request_id": request_id,
        }

        first_status, first = self._phone_request(
            "/v1/remote/commands", method="POST", payload=payload
        )
        retry_status, retry = self._phone_request(
            "/v1/remote/commands", method="POST", payload=payload
        )

        self.assertEqual(first_status, 202)
        self.assertEqual(retry_status, 202)
        self.assertEqual(first["id"], request_id)
        self.assertEqual(retry["id"], request_id)
        client = CloudPlannerClient(self._settings())
        self.assertEqual(client.claim_remote_command()["id"], request_id)
        self.assertIsNone(client.claim_remote_command())

    def test_request_id_cannot_be_reused_for_another_command(self) -> None:
        request_id = "b" * 32
        base = {"device_id": self.device_id, "request_id": request_id}
        first_status, _ = self._phone_request(
            "/v1/remote/commands",
            method="POST",
            payload={**base, "command": "status systemu"},
        )
        conflict_status, conflict = self._phone_request(
            "/v1/remote/commands",
            method="POST",
            payload={**base, "command": "status chmury"},
        )

        self.assertEqual(first_status, 202)
        self.assertEqual(conflict_status, 409)
        self.assertEqual(conflict["error"], "request_id_conflict")

    def test_invalid_request_id_is_rejected(self) -> None:
        status, payload = self._phone_request(
            "/v1/remote/commands",
            method="POST",
            payload={
                "device_id": self.device_id,
                "command": "status systemu",
                "request_id": "not-a-valid-request-id",
            },
        )

        self.assertEqual(status, 400)
        self.assertEqual(payload["error"], "invalid_request")

    def test_queue_transport_claims_and_acknowledges_after_report(self) -> None:
        status, submitted = self._phone_request(
            "/v1/remote/commands",
            method="POST",
            payload={
                "device_id": self.device_id,
                "command": "podaj godzinę",
            },
        )
        self.assertEqual(status, 202)
        queue = FakeQueueClient(
            [
                {
                    "id": submitted["id"],
                    "device_id": self.device_id,
                    "command": submitted["command"],
                    "kind": "command",
                }
            ]
        )
        client = CloudPlannerClient(
            self._settings(queue_url=self.queue_url), queue_client=queue
        )

        claimed = client.claim_remote_command()
        self.assertEqual(claimed["id"], submitted["id"])
        self.assertEqual(queue.receive_options["visibility_timeout"], 120)
        self.assertEqual(queue.deleted, [])

        completed = client.report_remote_command(
            claimed["id"], "completed", "Jest 21:30."
        )
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(
            queue.deleted,
            [("azure-message-id", "azure-pop-receipt")],
        )

    def test_probe_has_no_user_command_side_effect(self) -> None:
        status, submitted = self._phone_request(
            "/v1/remote/probe",
            method="POST",
            payload={"device_id": self.device_id},
        )
        self.assertEqual(status, 202)
        self.assertEqual(submitted["kind"], "probe")

        client = CloudPlannerClient(self._settings())
        claimed = client.claim_remote_command()
        self.assertEqual(claimed["kind"], "probe")
        completed = client.report_remote_command(
            claimed["id"], "completed", "Komputer jest online."
        )
        self.assertEqual(completed["message"], "Komputer jest online.")

    def test_invalid_queue_url_is_rejected_before_access(self) -> None:
        client = CloudPlannerClient(
            self._settings(
                queue_url=(
                    "https://evil.example/commands"
                    "?sv=x&se=x&sp=p&sr=q&sig=x"
                )
            ),
            queue_client=FakeQueueClient(),
        )
        with self.assertRaises(CloudPlannerUnavailable):
            client.claim_remote_command()

    def test_wrong_phone_token_is_rejected(self) -> None:
        status, payload = self._phone_request(
            "/v1/remote/commands",
            method="POST",
            payload={
                "device_id": self.device_id,
                "command": "status systemu",
            },
            token="wrong-token",
        )
        self.assertEqual(status, 401)
        self.assertEqual(payload["error"], "unauthorized")

    def test_rejected_post_closes_connection_before_unread_body(self) -> None:
        host, port = self.server.server_address
        connection = http.client.HTTPConnection(host, port, timeout=2)
        try:
            connection.request(
                "POST",
                "/v1/remote/commands",
                body=b"{}",
                headers={
                    "Authorization": "Bearer wrong-token",
                    "Content-Type": "application/json",
                },
            )
            response = connection.getresponse()
            response.read()
            self.assertEqual(response.status, 401)
            self.assertEqual(response.getheader("Connection"), "close")
            self.assertTrue(response.will_close)
        finally:
            connection.close()
    def test_easy_auth_owner_can_use_phone_without_pairing_token(self) -> None:
        owner = "77f4b7fe-8e18-498b-8898-84befa780edb"
        identity_store = MemoryRemoteCommandStore()
        identity_server = build_server(
            "127.0.0.1",
            0,
            config=ServiceConfig(
                api_token=self.desktop_token,
                phone_principal_id=owner,
                environment="test",
            ),
            remote_store=identity_store,
        )
        thread = threading.Thread(
            target=identity_server.serve_forever, daemon=True
        )
        thread.start()
        host, port = identity_server.server_address
        base_url = f"http://{host}:{port}"
        owner_headers = {
            "X-MS-CLIENT-PRINCIPAL-ID": owner,
            "X-MS-CLIENT-PRINCIPAL-IDP": "aad",
            "X-MS-CLIENT-PRINCIPAL-NAME": "Kacper Zakrzewski",
        }
        try:
            with urllib.request.urlopen(
                base_url + "/phone", timeout=2
            ) as response:
                login_page = response.read().decode("utf-8")
            self.assertIn("ZALOGUJ PRZEZ MICROSOFT", login_page)

            request = urllib.request.Request(
                base_url + "/phone", headers=owner_headers
            )
            with urllib.request.urlopen(request, timeout=2) as response:
                page = response.read().decode("utf-8")
            self.assertIn("SESJA AKTYWNA", page)

            request = urllib.request.Request(
                base_url + "/v1/phone/me", headers=owner_headers
            )
            with urllib.request.urlopen(request, timeout=2) as response:
                identity = json.loads(response.read().decode("utf-8"))
            self.assertEqual(identity["name"], "Kacper Zakrzewski")
            self.assertEqual(identity["session_minutes"], 60)

            payload = json.dumps(
                {"device_id": self.device_id, "command": "status systemu"}
            ).encode("utf-8")
            request = urllib.request.Request(
                base_url + "/v1/remote/commands",
                data=payload,
                method="POST",
                headers={
                    **owner_headers,
                    "Content-Type": "application/json",
                },
            )
            with urllib.request.urlopen(request, timeout=2) as response:
                submitted = json.loads(response.read().decode("utf-8"))
                self.assertEqual(response.status, 202)
            self.assertEqual(submitted["status"], "queued")
        finally:
            identity_server.shutdown()
            identity_server.server_close()
            thread.join(timeout=2)

    def test_easy_auth_rejects_wrong_owner_or_provider(self) -> None:
        owner = "77f4b7fe-8e18-498b-8898-84befa780edb"
        identity_server = build_server(
            "127.0.0.1",
            0,
            config=ServiceConfig(
                api_token=self.desktop_token,
                phone_principal_id=owner,
                environment="test",
            ),
            remote_store=MemoryRemoteCommandStore(),
        )
        thread = threading.Thread(
            target=identity_server.serve_forever, daemon=True
        )
        thread.start()
        host, port = identity_server.server_address
        try:
            cases = (("wrong-owner", "aad"), (owner, "github"))
            for principal_id, provider in cases:
                request = urllib.request.Request(
                    f"http://{host}:{port}/v1/phone/me",
                    headers={
                        "X-MS-CLIENT-PRINCIPAL-ID": principal_id,
                        "X-MS-CLIENT-PRINCIPAL-IDP": provider,
                    },
                )
                with self.assertRaises(urllib.error.HTTPError) as raised:
                    urllib.request.urlopen(request, timeout=2)
                self.assertEqual(raised.exception.code, 401)
        finally:
            identity_server.shutdown()
            identity_server.server_close()
            thread.join(timeout=2)

    def test_sensitive_command_never_enters_the_queue(self) -> None:
        status, payload = self._phone_request(
            "/v1/remote/commands",
            method="POST",
            payload={
                "device_id": self.device_id,
                "command": "użyj token=super-secret-value",
            },
        )
        self.assertEqual(status, 422)
        self.assertEqual(
            payload["error"], "sensitive_command_requires_local"
        )
        self.assertIsNone(self.store.claim_next(self.device_id))

    def test_health_reports_transport_without_exposing_tokens(self) -> None:
        with urllib.request.urlopen(
            self.base_url + "/health", timeout=2
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
        self.assertTrue(payload["remote_configured"])
        self.assertEqual(payload["remote_transport"], "https_poll")
        serialized = json.dumps(payload)
        self.assertNotIn(self.desktop_token, serialized)
        self.assertNotIn(self.phone_token, serialized)


class AzureRemoteStoreIdempotencyTests(unittest.TestCase):
    def test_retry_sends_only_one_azure_queue_message(self) -> None:
        store = object.__new__(AzureTableRemoteCommandStore)
        store._exists = FakeResourceExistsError
        store.table = FakeAzureTable()
        store.queue = FakeAzureSendQueue()
        request_id = "c" * 32

        first = store.create(
            "desktop-main",
            "status systemu",
            request_id=request_id,
        )
        retry = store.create(
            "desktop-main",
            "status systemu",
            request_id=request_id,
        )

        self.assertEqual(first["id"], request_id)
        self.assertEqual(retry["id"], request_id)
        self.assertEqual(len(store.queue.sent), 1)
        queued = json.loads(store.queue.sent[0][0])
        self.assertEqual(queued["id"], request_id)
        with self.assertRaises(RemoteStoreConflict):
            store.create(
                "desktop-main",
                "status chmury",
                request_id=request_id,
            )


if __name__ == "__main__":
    unittest.main()
