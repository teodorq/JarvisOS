from __future__ import annotations

import json
import threading
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timezone

from app.cloud.client import CloudPlannerClient, CloudPlannerSettings
from cloud_service.forex_status_store import MemoryForexStatusStore
from cloud_service.main import ServiceConfig, build_server
from tests.test_cloud_forex_status import sample_status


class RemoteForexStatusTests(unittest.TestCase):
    owner_id = "77f4b7fe-8e18-498b-8898-84befa780edb"

    def setUp(self) -> None:
        status = sample_status()
        status["observed_at"] = datetime.now(timezone.utc).isoformat()
        self.store = MemoryForexStatusStore(status)
        self.server = build_server(
            "127.0.0.1",
            0,
            config=ServiceConfig(
                api_token="desktop-token-with-enough-entropy",
                environment="test",
                phone_principal_id=self.owner_id,
            ),
            forex_status_store=self.store,
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

    def owner_request(self, path: str) -> urllib.request.Request:
        return urllib.request.Request(
            self.base_url + path,
            headers={
                "X-MS-CLIENT-PRINCIPAL-ID": self.owner_id,
                "X-MS-CLIENT-PRINCIPAL-IDP": "aad",
            },
        )

    def test_owner_can_read_sanitized_json_status(self) -> None:
        with urllib.request.urlopen(
            self.owner_request("/v1/forex/status"), timeout=2
        ) as response:
            value = json.loads(response.read().decode("utf-8"))

        self.assertEqual(value["cycle_id"], "cycle-123")
        self.assertFalse(value["real_money_access"])
        self.assertIn("fresh", value)
        self.assertNotIn("secret", value)

    def test_desktop_client_can_read_status_with_existing_api_token(self) -> None:
        client = CloudPlannerClient(CloudPlannerSettings(
            base_url=self.base_url,
            api_token="desktop-token-with-enough-entropy",
            timeout_seconds=2,
        ))

        value = client.forex_status()

        self.assertEqual(value["cycle_id"], "cycle-123")
        self.assertFalse(value["live_orders_sent"])
        self.assertNotIn("secret", value)

    def test_status_api_rejects_missing_or_wrong_owner(self) -> None:
        requests = (
            urllib.request.Request(self.base_url + "/v1/forex/status"),
            urllib.request.Request(
                self.base_url + "/v1/forex/status",
                headers={
                    "X-MS-CLIENT-PRINCIPAL-ID": "wrong-owner",
                    "X-MS-CLIENT-PRINCIPAL-IDP": "aad",
                },
            ),
        )
        for request in requests:
            with self.subTest(headers=dict(request.headers)):
                with self.assertRaises(urllib.error.HTTPError) as caught:
                    urllib.request.urlopen(request, timeout=2)
                self.assertEqual(caught.exception.code, 401)

    def test_owner_page_is_script_free_and_explicitly_paper(self) -> None:
        status = sample_status()
        status["observed_at"] = datetime.now(timezone.utc).isoformat()
        status["v3_activation_status"] = (
            "SHADOW_SIMULATION_ACTIVATION_BLOCKED"
        )
        status["v3_activation_reason"] = "V3_FORWARD_EVIDENCE_INCOMPLETE"
        status["v3_plan_observation_status"] = (
            "SHADOW_PLAN_OBSERVATION_WAITING"
        )
        status["v3_plan_reason"] = "WAITING_FOR_FORWARD_SAMPLE"
        status["v3_decision_status"] = ""
        status["activity_events"] = [{
            "sequence": 1,
            "event_id": "000000000000000000000001",
            "occurred_at": "2026-11-03T10:01:00+00:00",
            "kind": "FOREX_V3_FORWARD_PROGRESS",
            "state": "brief",
            "message": (
                "<script>must-not-run</script> Forex V3: zweryfikowana "
                "probka osiagnela 10/20 cykli. "
                "To informacja o postepie — nie wlacza LIVE."
            ),
        }]
        self.store.write(status)
        with urllib.request.urlopen(
            self.owner_request("/trading"), timeout=2
        ) as response:
            body = response.read().decode("utf-8")
            policy = response.headers["Content-Security-Policy"]

        self.assertIn("WYLACZNIE PAPER", body)
        self.assertIn("EUR_USD", body)
        self.assertIn("BIEZACY CYKL", body)
        self.assertIn("Brak bezpiecznego sygnalu wejscia", body)
        self.assertIn("DLACZEGO PARA BYLA ZABLOKOWANA", body)
        self.assertIn("brak potwierdzenia z drugiego zrodla", body)
        self.assertIn("DLACZEGO V3 PODJAL TAKA DECYZJE", body)
        self.assertIn("brak nowego przeciecia srednich", body)
        self.assertIn("sila sygnalu V3 jest zbyt mala", body)
        self.assertIn("POSTEP PROBKI V3", body)
        self.assertIn("4 / 20", body)
        self.assertIn("1 / 3", body)
        self.assertIn("Trwa zbieranie niezaleznej probki V3", body)
        self.assertIn("Pozostalo cykli</span>16", body)
        self.assertIn("Pozostalo dni rynkowych</span>2", body)
        self.assertNotIn("V3_FORWARD_EVIDENCE_INCOMPLETE", body)
        self.assertIn("BRAMKI V3 &mdash; CO DALEJ", body)
        self.assertIn("DOWODY FORWARD", body)
        self.assertIn("W TOKU", body)
        self.assertIn("CZEKA NA PROBKE", body)
        self.assertIn("ZAWSZE ZABLOKOWANE", body)
        self.assertNotIn("SHADOW_SIMULATION_ACTIVATION_BLOCKED", body)
        self.assertIn("OSTATNIE ZDARZENIA PAPER", body)
        self.assertIn("POSTEP V3", body)
        self.assertIn("zweryfikowana probka osiagnela 10/20 cykli", body)
        self.assertIn("&lt;script&gt;must-not-run&lt;/script&gt;", body)
        self.assertNotIn("FOREX_V3_FORWARD_PROGRESS", body)
        self.assertIn("nigdy automatycznie nie wlacza LIVE", body)
        self.assertNotIn("<script", body.lower())
        self.assertIn("script-src 'none'", policy)

    def test_owner_page_labels_new_shadow_initialization_event(self) -> None:
        status = sample_status()
        status["observed_at"] = datetime.now(timezone.utc).isoformat()
        status["activity_events"] = [{
            "sequence": 1,
            "event_id": "000000000000000000000001",
            "occurred_at": "2026-11-03T10:01:00+00:00",
            "kind": "FOREX_V3_SHADOW_INITIALIZED",
            "state": "important",
            "message": "Pusty i nieaktywny portfel V3 SHADOW jest gotowy.",
        }]
        self.store.write(status)

        with urllib.request.urlopen(
            self.owner_request("/trading"), timeout=2
        ) as response:
            body = response.read().decode("utf-8")

        self.assertIn("PORTFEL V3 UTWORZONY", body)
        self.assertNotIn("FOREX_V3_SHADOW_INITIALIZED", body)

    def test_owner_page_labels_shadow_simulation_activation_event(self) -> None:
        status = sample_status()
        status["observed_at"] = datetime.now(timezone.utc).isoformat()
        status["activity_events"] = [{
            "sequence": 1,
            "event_id": "000000000000000000000001",
            "occurred_at": "2026-11-03T10:01:00+00:00",
            "kind": "FOREX_V3_SHADOW_SIMULATION_ACTIVATED",
            "state": "important",
            "message": "Izolowana symulacja V3 PAPER zostala uruchomiona.",
        }]
        self.store.write(status)

        with urllib.request.urlopen(
            self.owner_request("/trading"), timeout=2
        ) as response:
            body = response.read().decode("utf-8")

        self.assertIn("SYMULACJA V3 AKTYWNA", body)
        self.assertNotIn("FOREX_V3_SHADOW_SIMULATION_ACTIVATED", body)

    def test_owner_page_labels_v3_shadow_fill_events(self) -> None:
        status = sample_status()
        status["observed_at"] = datetime.now(timezone.utc).isoformat()
        status["activity_events"] = [
            {
                "sequence": 1,
                "event_id": "000000000000000000000001",
                "occurred_at": "2026-11-08T13:02:20+00:00",
                "kind": "FOREX_V3_SHADOW_POSITION_OPENED",
                "state": "important",
                "message": "V3 SHADOW PAPER otworzył pozycję symulowaną.",
            },
            {
                "sequence": 2,
                "event_id": "000000000000000000000002",
                "occurred_at": "2026-11-08T14:02:20+00:00",
                "kind": "FOREX_V3_SHADOW_POSITION_CLOSED",
                "state": "important",
                "message": "V3 SHADOW PAPER zamknął pozycję symulowaną.",
            },
        ]
        self.store.write(status)

        with urllib.request.urlopen(
            self.owner_request("/trading"), timeout=2
        ) as response:
            body = response.read().decode("utf-8")

        self.assertIn("V3 OTWARCIE PAPER", body)
        self.assertIn("V3 ZAMKNIECIE PAPER", body)
        self.assertNotIn("FOREX_V3_SHADOW_POSITION_OPENED", body)
        self.assertNotIn("FOREX_V3_SHADOW_POSITION_CLOSED", body)

    def test_owner_page_separates_v3_result_from_review_sample(self) -> None:
        status = sample_status()
        status["observed_at"] = datetime.now(timezone.utc).isoformat()
        self.store.write(status)

        with urllib.request.urlopen(
            self.owner_request("/trading"), timeout=2
        ) as response:
            body = response.read().decode("utf-8")

        self.assertIn("PROBKA WYNIKOW V3", body)
        self.assertIn("JARVIS nadal zbiera zamkniete transakcje", body)
        self.assertIn("Wazne zamkniecia</span>4 / 30", body)
        self.assertIn("Pozostalo do przegladu</span>26", body)
        self.assertIn("Nie potwierdza rentownosci", body)
        self.assertNotIn("COLLECTING_SAMPLE", body)

    def test_owner_page_labels_complete_v3_sample_as_manual_review_only(
        self,
    ) -> None:
        status = sample_status()
        status["observed_at"] = datetime.now(timezone.utc).isoformat()
        status["v3_performance"]["status"] = "READY_FOR_MANUAL_REVIEW"
        status["v3_performance"]["valid_closed_trade_count"] = 30
        status["v3_performance"]["sample_progress_pct"] = "100.00"
        self.store.write(status)

        with urllib.request.urlopen(
            self.owner_request("/trading"), timeout=2
        ) as response:
            body = response.read().decode("utf-8")

        self.assertIn("Probka gotowa do recznej oceny", body)
        self.assertIn("Wazne zamkniecia</span>30 / 30", body)
        self.assertIn("Pozostalo do przegladu</span>0", body)
        self.assertIn("nadal nie potwierdza zysku i nie wlacza LIVE", body)
        self.assertNotIn("READY_FOR_MANUAL_REVIEW", body)

    def test_owner_page_hides_stale_v3_performance_metrics(self) -> None:
        status = sample_status()
        status["observed_at"] = "2026-01-01T00:00:00+00:00"
        status["v3_performance"]["profit_factor"] = "9.8765"
        status["v3_realized_pnl_pln"] = "987.65"
        self.store.write(status)

        with urllib.request.urlopen(
            self.owner_request("/trading"), timeout=2
        ) as response:
            body = response.read().decode("utf-8")

        self.assertIn("Wyniki ukryte do czasu swiezego raportu", body)
        self.assertIn("Wazne zamkniecia</span>N/D / N/D", body)
        self.assertNotIn("9.8765", body)
        self.assertNotIn("987.65", body)

    def test_owner_stage_map_keeps_existing_shadow_separate_from_live(
        self,
    ) -> None:
        status = sample_status()
        status["observed_at"] = datetime.now(timezone.utc).isoformat()
        self.store.write(status)

        with urllib.request.urlopen(
            self.owner_request("/trading"), timeout=2
        ) as response:
            body = response.read().decode("utf-8")

        self.assertIn("AKTYWNY PAPER", body)
        self.assertIn("PROBKA PLANOW ZAKONCZONA", body)
        self.assertIn("AKTYWNA - TYLKO PAPER", body)
        self.assertIn("ZAWSZE ZABLOKOWANE", body)
        self.assertIn("Bramki sa niezalezne", body)
        self.assertNotIn("ALREADY_ACTIVE", body)
        self.assertNotIn("SHADOW_SIMULATION_CYCLE_COMPLETED", body)

    def test_stale_report_hides_active_shadow_gate_state(self) -> None:
        status = sample_status()
        status["observed_at"] = "2020-01-01T00:00:00+00:00"
        self.store.write(status)

        with urllib.request.urlopen(
            self.owner_request("/trading"), timeout=2
        ) as response:
            body = response.read().decode("utf-8")

        self.assertIn("DANE NIEAKTUALNE", body)
        self.assertIn("NIEDOSTEPNE", body)
        self.assertIn("ZAWSZE ZABLOKOWANE", body)
        self.assertNotIn("AKTYWNY PAPER", body)
        self.assertNotIn("AKTYWNA - TYLKO PAPER", body)

    def test_report_not_ready_returns_controlled_503(self) -> None:
        self.server.forex_status_store = MemoryForexStatusStore()
        with self.assertRaises(urllib.error.HTTPError) as caught:
            urllib.request.urlopen(self.owner_request("/trading"), timeout=2)
        self.assertEqual(caught.exception.code, 503)
        body = caught.exception.read().decode("utf-8")
        self.assertIn("RAPORT JESZCZE NIEDOSTEPNY", body)


if __name__ == "__main__":
    unittest.main()
