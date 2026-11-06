from __future__ import annotations

from app.trading.forex_v3_shadow_initialization_notifications import (
    v3_shadow_initialization_milestone,
)
from tests.test_forex_activity_journal import (
    _complete_v3_forward_report,
    _partial_v3_forward_report,
)


def _payload() -> dict:
    report = _complete_v3_forward_report()
    return {
        "observed_at": "2026-11-06T10:00:00+00:00",
        "broker_orders_sent": False,
        "live_orders_sent": False,
        "real_money_access": False,
        "v3_forward_evidence": report,
        "v3_shadow_initialization": {
            "status": "INITIALIZED_SHADOW_INACTIVE",
            "candidate_id": report["candidate_id"],
            "shadow_ledger_created": True,
            "shadow_execution_enabled": False,
            "paper_orders_sent": False,
            "broker_orders_sent": False,
            "live_orders_sent": False,
            "network_access": False,
            "real_money_access": False,
        },
    }


def test_valid_initialization_emits_one_deduplicated_milestone() -> None:
    fingerprint, event = v3_shadow_initialization_milestone(_payload())

    assert len(fingerprint) == 64
    assert event is not None
    assert event["kind"] == "FOREX_V3_SHADOW_INITIALIZED"
    assert event["state"] == "important"
    assert v3_shadow_initialization_milestone(
        _payload(), completed_fingerprint=fingerprint
    ) == (fingerprint, None)


def test_mismatched_candidate_or_incomplete_evidence_is_rejected() -> None:
    mismatch = _payload()
    mismatch["v3_shadow_initialization"]["candidate_id"] = "OTHER_CANDIDATE"
    incomplete = _payload()
    incomplete["v3_forward_evidence"] = _partial_v3_forward_report(19)

    assert v3_shadow_initialization_milestone(mismatch) == ("", None)
    assert v3_shadow_initialization_milestone(incomplete) == ("", None)


def test_existing_or_executable_shadow_is_rejected() -> None:
    existing = _payload()
    existing["v3_shadow_initialization"]["status"] = (
        "ALREADY_INITIALIZED_SHADOW_INACTIVE"
    )
    existing["v3_shadow_initialization"]["shadow_ledger_created"] = False
    executable = _payload()
    executable["v3_shadow_initialization"]["shadow_execution_enabled"] = True

    assert v3_shadow_initialization_milestone(existing) == ("", None)
    assert v3_shadow_initialization_milestone(executable) == ("", None)
