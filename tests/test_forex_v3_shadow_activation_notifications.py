from __future__ import annotations

from app.trading.forex_v3_shadow_activation_notifications import (
    v3_shadow_activation_milestone,
)


def _payload() -> dict:
    return {
        "observed_at": "2026-11-07T22:00:00+00:00",
        "broker_orders_sent": False,
        "live_orders_sent": False,
        "real_money_access": False,
        "v3_shadow_activation": {
            "status": "SIMULATION_ACTIVATED",
            "mode": "FOREX_V3_SHADOW_SIMULATION_CONTROL",
            "simulation_activated": True,
            "shadow_simulation_enabled": True,
            "shadow_execution_enabled": True,
            "review_fingerprint_sha256": "d" * 64,
            "candidate_id": "FOREX_STRENGTH_V3R2_20261104",
            "paper_orders_sent": False,
            "broker_orders_sent": False,
            "live_orders_sent": False,
            "network_access": False,
            "real_money_access": False,
        },
    }


def test_valid_activation_emits_one_deduplicated_milestone() -> None:
    fingerprint, event = v3_shadow_activation_milestone(_payload())

    assert len(fingerprint) == 64
    assert event is not None
    assert event["kind"] == "FOREX_V3_SHADOW_SIMULATION_ACTIVATED"
    assert v3_shadow_activation_milestone(
        _payload(), completed_fingerprint=fingerprint
    ) == (fingerprint, None)


def test_existing_or_unsafe_activation_is_rejected() -> None:
    existing = _payload()
    existing["v3_shadow_activation"]["status"] = "ALREADY_ACTIVE"
    existing["v3_shadow_activation"]["simulation_activated"] = False
    unsafe = _payload()
    unsafe["v3_shadow_activation"]["live_orders_sent"] = True

    assert v3_shadow_activation_milestone(existing) == ("", None)
    assert v3_shadow_activation_milestone(unsafe) == ("", None)


def test_invalid_review_identity_is_rejected() -> None:
    invalid_fingerprint = _payload()
    invalid_fingerprint["v3_shadow_activation"][
        "review_fingerprint_sha256"
    ] = "not-a-sha"
    invalid_candidate = _payload()
    invalid_candidate["v3_shadow_activation"]["candidate_id"] = "bad candidate"

    assert v3_shadow_activation_milestone(invalid_fingerprint) == ("", None)
    assert v3_shadow_activation_milestone(invalid_candidate) == ("", None)
