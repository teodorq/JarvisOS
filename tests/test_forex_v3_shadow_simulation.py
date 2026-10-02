from __future__ import annotations

from copy import deepcopy

from app.trading.forex_v3_shadow_simulation import (
    ForexV3ShadowSimulationReadiness,
)


class StaticShadowReadiness:
    def __init__(self, value: dict) -> None:
        self.value = deepcopy(value)

    def status(self) -> dict:
        return deepcopy(self.value)


class StaticPlanJournal:
    def __init__(self, value: dict) -> None:
        self.value = deepcopy(value)

    def summary(self) -> dict:
        return deepcopy(self.value)


def _shadow() -> dict:
    return {
        "status": "SHADOW_INITIALIZED_INACTIVE",
        "mode": "FOREX_V3_SHADOW_READINESS_ONLY",
        "shadow_execution_enabled": False,
        "paper_orders_sent": False,
        "broker_orders_sent": False,
        "live_orders_sent": False,
        "network_access": False,
        "real_money_access": False,
    }


def _plans(status: str = "COLLECTING_SHADOW_PLANS") -> dict:
    return {
        "status": status,
        "mode": "FOREX_V3_SHADOW_PLAN_JOURNAL_ONLY",
        "audit_chain_valid": True,
        "plan_count": 4,
        "minimum_plan_count": 20,
        "remaining_plan_count": 16,
        "market_day_count": 1,
        "minimum_market_day_count": 3,
        "remaining_market_day_count": 2,
        "entry_plan_count": 0,
        "minimum_entry_plan_count": 3,
        "remaining_entry_plan_count": 3,
        "plan_sample_complete": False,
        "signal_scarcity_detected": False,
        "signal_sample_sufficient": False,
        "simulation_review_ready": False,
        "simulation_activation_ready": False,
        "performance_validated": False,
        "shadow_execution_enabled": False,
        "paper_orders_sent": False,
        "broker_orders_sent": False,
        "live_orders_sent": False,
        "network_access": False,
        "real_money_access": False,
    }


def _gate(shadow: dict, plans: dict) -> ForexV3ShadowSimulationReadiness:
    return ForexV3ShadowSimulationReadiness(
        shadow_readiness=StaticShadowReadiness(shadow),
        plan_journal=StaticPlanJournal(plans),
    )


def _assert_execution_disabled(result: dict) -> None:
    assert result["simulation_initialized"] is False
    assert result["shadow_simulation_enabled"] is False
    assert result["shadow_execution_enabled"] is False
    assert result["paper_orders_sent"] is False
    assert result["broker_orders_sent"] is False
    assert result["live_orders_sent"] is False
    assert result["network_access"] is False
    assert result["real_money_access"] is False


def test_incomplete_plan_sample_waits_without_initializing_simulation() -> None:
    result = _gate(_shadow(), _plans()).status()

    assert result["status"] == "WAITING_FOR_PLAN_SAMPLE"
    assert result["plan_count"] == 4
    assert result["remaining_plan_count"] == 16
    assert result["remaining_market_day_count"] == 2
    assert result["remaining_entry_plan_count"] == 3
    assert result["simulation_review_ready"] is False
    assert result["manual_simulation_initialization_required"] is False
    _assert_execution_disabled(result)


def test_complete_sample_with_too_few_entries_blocks_simulation() -> None:
    plans = _plans("SHADOW_PLAN_SAMPLE_SIGNAL_SCARCE")
    plans.update({
        "plan_count": 20,
        "remaining_plan_count": 0,
        "market_day_count": 3,
        "remaining_market_day_count": 0,
        "plan_sample_complete": True,
        "signal_scarcity_detected": True,
    })

    result = _gate(_shadow(), plans).status()

    assert result["status"] == "BLOCKED_SIGNAL_SCARCITY"
    assert result["reason"] == "INSUFFICIENT_ENTRY_PLAN_FREQUENCY"
    assert result["entry_plan_count"] == 0
    assert result["remaining_entry_plan_count"] == 3
    assert result["simulation_review_ready"] is False
    _assert_execution_disabled(result)


def test_verified_sample_only_arms_manual_simulation_initialization() -> None:
    plans = _plans("SHADOW_PLAN_SAMPLE_REVIEW_READY")
    plans.update({
        "plan_count": 20,
        "remaining_plan_count": 0,
        "market_day_count": 3,
        "remaining_market_day_count": 0,
        "entry_plan_count": 3,
        "remaining_entry_plan_count": 0,
        "plan_sample_complete": True,
        "signal_sample_sufficient": True,
        "simulation_review_ready": True,
        "review_fingerprint_sha256": "a" * 64,
    })

    result = _gate(_shadow(), plans).status()

    assert result["status"] == (
        "READY_FOR_MANUAL_SIMULATION_INITIALIZATION"
    )
    assert result["review_fingerprint_sha256"] == "a" * 64
    assert result["simulation_review_ready"] is True
    assert result["manual_simulation_initialization_required"] is True
    assert result["simulation_initialized"] is False
    assert result["performance_validated"] is False
    assert result["current_paper_strategy_changed"] is False
    _assert_execution_disabled(result)


def test_unsafe_or_inconsistent_source_fails_closed() -> None:
    unsafe_shadow = _shadow()
    unsafe_shadow["live_orders_sent"] = True
    unsafe = _gate(unsafe_shadow, _plans()).status()
    assert unsafe["status"] == "BLOCKED_SIMULATION_READINESS_INVALID"
    assert unsafe["reason"] == "SHADOW_READINESS_INVALID"
    _assert_execution_disabled(unsafe)

    invalid_plans = _plans()
    invalid_plans["audit_chain_valid"] = False
    invalid = _gate(_shadow(), invalid_plans).status()
    assert invalid["status"] == "BLOCKED_SIMULATION_READINESS_INVALID"
    assert invalid["reason"] == "SHADOW_PLAN_JOURNAL_INVALID"
    _assert_execution_disabled(invalid)
