from __future__ import annotations

from datetime import datetime, timezone

from app.cloud.forex_status import (
    CloudForexStatusSource,
    project_cloud_forex_status,
)
from cloud_service.forex_status_store import forex_status_view
from tests.test_cloud_forex_status import sample_status


NOW = datetime(2026, 11, 3, 11, 0, tzinfo=timezone.utc)


class _Client:
    is_configured = True

    def __init__(self, value: dict) -> None:
        self.value = value
        self.calls = 0

    def forex_status(self) -> dict:
        self.calls += 1
        return dict(self.value)


def test_fresh_cloud_status_projects_current_paper_position() -> None:
    payload = forex_status_view(sample_status(), now=NOW)

    snapshot = project_cloud_forex_status(payload, now=NOW)

    assert snapshot["status"] == "READY"
    assert snapshot["source"] == "AZURE_PAPER_STATUS"
    assert snapshot["data_fresh"] is True
    assert snapshot["positions"][0]["pair"] == "EUR_USD"
    assert snapshot["last_runtime_cycle"]["decision"] == "NO_ENTRY_SIGNAL"
    assert snapshot["last_runtime_cycle"]["ready_pair_count"] == 6
    assert snapshot["last_runtime_cycle"]["blocked_pair_count"] == 1
    assert snapshot["last_runtime_cycle"]["execution_count"] == 0
    assert snapshot["last_runtime_cycle"]["reason_codes"] == {
        "NO_ENTRY_SIGNAL": 6,
        "SPREAD_TOO_WIDE": 1,
    }
    assert snapshot["last_v3_cycle"] == {
        "available": True,
        "initialization_status": "ALREADY_INITIALIZED_SHADOW_INACTIVE",
        "initialization_reason": "",
        "activation_status": "ALREADY_ACTIVE",
        "activation_reason": "",
        "status": "SHADOW_PLAN_OBSERVED",
        "plan_reason": "",
        "decision": "NO_ACTION",
        "simulation_reason": "",
        "ready_pair_count": 6,
        "blocked_pair_count": 1,
        "instruction_count": 0,
        "execution_count": 0,
        "reason_codes": {
            "NO_NEW_CROSSOVER": 5,
            "CANDIDATE_V3_SIGNAL_STRENGTH_TOO_LOW": 1,
            "SPREAD_TOO_WIDE": 1,
        },
        "forward_evidence": {
            "status": "COLLECTING_FORWARD_EVIDENCE",
            "candidate_id": "FOREX_STRENGTH_V3R2_20261104",
            "source_state_valid": True,
            "sample_complete": False,
            "accepted_cycle_count": 4,
            "minimum_cycle_count": 20,
            "accepted_market_day_count": 1,
            "minimum_market_day_count": 3,
            "invalid_cycle_count": 0,
            "exclusions": {"SUPERSEDED_CANDIDATE": 12},
            "invalid_issues": {},
        },
        "paper_orders_sent": False,
        "broker_orders_sent": False,
        "live_orders_sent": False,
        "real_money_access": False,
    }
    assert snapshot["broker_orders_sent"] is False
    assert snapshot["live_orders_sent"] is False
    assert snapshot["real_money_access"] is False


def test_desktop_clock_blocks_stale_payload_even_if_server_claims_fresh() -> None:
    payload = forex_status_view(sample_status(), now=NOW)
    payload["fresh"] = True

    snapshot = project_cloud_forex_status(
        payload,
        now=datetime(2026, 11, 4, 11, 0, tzinfo=timezone.utc),
    )

    assert snapshot["status"] == "STALE_DATA_BLOCKED"
    assert snapshot["data_fresh"] is False
    assert snapshot["positions"] == []
    assert snapshot["position_count"] == 0
    assert "nieaktualne" in snapshot["message"]


def test_unsafe_cloud_flags_block_the_entire_current_state() -> None:
    payload = forex_status_view(sample_status(), now=NOW)
    payload["real_money_access"] = True

    snapshot = project_cloud_forex_status(payload, now=NOW)

    assert snapshot["status"] == "STALE_DATA_BLOCKED"
    assert snapshot["positions"] == []
    assert "PAPER ONLY" in snapshot["message"]


def test_inconsistent_v3_diagnostics_fail_closed() -> None:
    payload = forex_status_view(sample_status(), now=NOW)
    payload["v3_instruction_count"] = 0
    payload["v3_execution_count"] = 1

    snapshot = project_cloud_forex_status(payload, now=NOW)

    assert snapshot["status"] == "STALE_DATA_BLOCKED"
    assert snapshot["last_v3_cycle"]["available"] is False
    assert snapshot["positions"] == []


def test_inconsistent_complete_v3r2_evidence_fails_closed() -> None:
    payload = forex_status_view(sample_status(), now=NOW)
    payload["v3_forward_sample_complete"] = True

    snapshot = project_cloud_forex_status(payload, now=NOW)

    assert snapshot["status"] == "STALE_DATA_BLOCKED"
    assert snapshot["last_v3_cycle"]["available"] is False


def test_source_refreshes_the_private_status_without_ui_thread_networking() -> None:
    payload = forex_status_view(sample_status(), now=NOW)
    client = _Client(payload)
    source = CloudForexStatusSource(client, now=lambda: NOW)

    source.refresh_now()
    snapshot = source.snapshot()

    assert client.calls == 1
    assert snapshot is not None
    assert snapshot["data_fresh"] is True
    assert snapshot["positions"][0]["pair"] == "EUR_USD"
