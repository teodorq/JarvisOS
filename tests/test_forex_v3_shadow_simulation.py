from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.trading.forex_models import (
    ForexBar,
    ForexQuote,
    ForexSafetyContext,
    MAJOR_FOREX_PAIRS,
    USD_PLN_CONVERSION_PAIR,
)
from app.trading.forex_risk import ForexRateBook
from app.trading.forex_v3_shadow_ledger import ForexV3ShadowLedger
from app.trading.forex_v3_shadow_planner import ForexV3ShadowPlanner
from app.trading.forex_v3_shadow_simulation import (
    ForexV3ShadowSimulationActivator,
    ForexV3ShadowSimulationEngine,
    ForexV3ShadowSimulationReadiness,
)
from app.trading.models import TradingValidationError
from app.trading.paper_broker import LiveTradingBlockedError


NOW = datetime(2026, 10, 16, 12, tzinfo=timezone.utc)
BASE = {
    "EUR_USD": Decimal("1.1000"),
    "GBP_USD": Decimal("1.2800"),
    "USD_JPY": Decimal("150.00"),
    "USD_CHF": Decimal("0.9000"),
    "AUD_USD": Decimal("0.6600"),
    "USD_CAD": Decimal("1.3500"),
    "NZD_USD": Decimal("0.6100"),
}


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


class ReadySimulation:
    fingerprint = "c" * 64

    @classmethod
    def status(cls) -> dict:
        return {
            "status": "READY_FOR_MANUAL_SIMULATION_INITIALIZATION",
            "reason": "PLAN_SAMPLE_AND_SIGNAL_FREQUENCY_VERIFIED",
            "review_fingerprint_sha256": cls.fingerprint,
        }


class ActiveShadowReadiness:
    @staticmethod
    def status() -> dict:
        return {
            "status": "SHADOW_SIMULATION_ACTIVE",
            "shadow_ledger_initialized": True,
            "shadow_execution_enabled": True,
        }


def _inactive_ledger(tmp_path) -> ForexV3ShadowLedger:
    ledger = ForexV3ShadowLedger(tmp_path)

    def initialize(state: dict) -> None:
        state["initialization"] = {
            "status": "INITIALIZED_SHADOW_INACTIVE",
            "initialized_at": NOW.isoformat(),
            "forward_evidence_content_sha256": "a" * 64,
            "source_head_hash": "b" * 64,
            "source_cutoff_sequence": 106,
            "simulation_activated_at": "",
            "simulation_review_fingerprint_sha256": "",
            "execution_enabled": False,
        }
        ledger.append_event(
            state,
            "V3_SHADOW_INITIALIZED_INACTIVE",
            {"execution_enabled": False},
            created_at=NOW,
        )

    ledger.transaction(initialize)
    return ledger


def _market(now: datetime = NOW):
    quotes = {}
    bars = {}
    contexts = {}
    for pair in MAJOR_FOREX_PAIRS:
        prices = [BASE[pair.symbol]] * 31
        if pair.symbol == "EUR_USD":
            prices[-1] += pair.pip_size * Decimal("20")
        bars[pair.symbol] = [
            ForexBar.create(
                pair=pair,
                timestamp=now - timedelta(minutes=15 * (30 - index)),
                open=price,
                high=price + pair.pip_size,
                low=price - pair.pip_size,
                close=price,
                tick_volume=100,
            )
            for index, price in enumerate(prices)
        ]
        half = pair.pip_size / Decimal("2")
        quotes[pair.symbol] = ForexQuote.create(
            pair=pair,
            bid=prices[-1] - half,
            ask=prices[-1] + half,
            timestamp=now,
        )
        contexts[pair.symbol] = ForexSafetyContext(
            observed_at=now,
            market_open=True,
            calendar_ready=True,
            high_impact_event_blocked=False,
            conversion_to_pln_ready=True,
            independent_source_count=2,
        )
    conversions = [ForexQuote.create(
        pair=USD_PLN_CONVERSION_PAIR,
        bid="3.999",
        ask="4.001",
        timestamp=now,
    )]
    return quotes, bars, contexts, conversions


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


def test_activation_requires_exact_review_fingerprint(tmp_path) -> None:
    ledger = _inactive_ledger(tmp_path)
    activator = ForexV3ShadowSimulationActivator(
        tmp_path,
        readiness=ReadySimulation(),
        ledger=ledger,
    )

    blocked = activator.activate(
        confirmation="ACTIVATE V3 SHADOW wrong",
        now=NOW + timedelta(minutes=1),
    )
    unchanged = ledger.snapshot()

    assert blocked["status"] == "BLOCKED_SIMULATION_ACTIVATION"
    assert blocked["reason"] == "CONFIRMATION_MISMATCH"
    assert unchanged["initialization"]["status"] == (
        "INITIALIZED_SHADOW_INACTIVE"
    )
    assert unchanged["initialization"]["execution_enabled"] is False


def test_activation_creates_audited_paper_only_simulation_state(
    tmp_path,
) -> None:
    ledger = _inactive_ledger(tmp_path)
    activator = ForexV3ShadowSimulationActivator(
        tmp_path,
        readiness=ReadySimulation(),
        ledger=ledger,
    )

    result = activator.activate(
        confirmation=activator.confirmation_for(ReadySimulation.fingerprint),
        now=NOW + timedelta(minutes=1),
    )
    state = ledger.snapshot()

    assert result["status"] == "SIMULATION_ACTIVATED"
    assert result["shadow_simulation_enabled"] is True
    assert result["shadow_execution_enabled"] is True
    assert result["broker_orders_sent"] is False
    assert result["live_orders_sent"] is False
    assert result["real_money_access"] is False
    assert state["initialization"]["status"] == (
        "INITIALIZED_SHADOW_SIMULATION_ACTIVE"
    )
    assert state["initialization"]["execution_enabled"] is True
    assert state["initialization"][
        "simulation_review_fingerprint_sha256"
    ] == ReadySimulation.fingerprint
    assert state["audit"][-1]["event_type"] == (
        "V3_SHADOW_SIMULATION_ACTIVATED"
    )
    assert ForexV3ShadowLedger.verify_audit(state) is True


def test_active_v3_executes_only_in_isolated_shadow_ledger(tmp_path) -> None:
    ledger = _inactive_ledger(tmp_path)
    activator = ForexV3ShadowSimulationActivator(
        tmp_path,
        readiness=ReadySimulation(),
        ledger=ledger,
    )
    activated = activator.activate(
        confirmation=activator.confirmation_for(ReadySimulation.fingerprint),
        now=NOW + timedelta(minutes=1),
    )
    assert activated["status"] == "SIMULATION_ACTIVATED"
    quotes, bars, contexts, conversions = _market(NOW + timedelta(minutes=2))
    planner = ForexV3ShadowPlanner(
        tmp_path,
        readiness=ActiveShadowReadiness(),
        ledger=ledger,
    )
    plan = planner.plan(
        quotes=quotes,
        bars=bars,
        contexts=contexts,
        conversion_quotes=conversions,
        cycle_id="shadow-simulation-cycle-0001",
        now=NOW + timedelta(minutes=2),
    )
    rates = ForexRateBook(
        (*quotes.values(), *conversions),
        now=NOW + timedelta(minutes=2),
    )
    engine = ForexV3ShadowSimulationEngine(tmp_path, ledger=ledger)

    execution = engine.apply_plan(
        plan,
        quotes=quotes,
        rates=rates,
        cycle_id=plan["cycle_id"],
        now=NOW + timedelta(minutes=2),
    )
    replay = engine.apply_plan(
        plan,
        quotes=quotes,
        rates=rates,
        cycle_id=plan["cycle_id"],
        now=NOW + timedelta(minutes=2),
    )
    state = ledger.snapshot()

    assert plan["decision_status"] == "ENTRIES_READY"
    assert execution["status"] == "APPLIED"
    assert execution["mode"] == "FOREX_V3_SHADOW_PAPER_ONLY"
    assert execution["live_orders_sent"] is False
    assert replay["idempotent_replay"] is True
    assert len(state["positions"]) == 1
    assert state["fills"][0]["fill_id"].startswith("forex-v3-shadow-")
    assert state["audit"][-1]["event_type"] == (
        "FOREX_V3_SHADOW_SIMULATION_CYCLE"
    )
    assert ForexV3ShadowLedger.verify_audit(state) is True
    assert not (tmp_path / "data/trading/forex_paper_ledger.json").exists()


def test_v3_executor_rejects_tampering_cycle_mismatch_and_live_orders(
    tmp_path,
) -> None:
    ledger = _inactive_ledger(tmp_path)
    activator = ForexV3ShadowSimulationActivator(
        tmp_path,
        readiness=ReadySimulation(),
        ledger=ledger,
    )
    activator.activate(
        confirmation=activator.confirmation_for(ReadySimulation.fingerprint),
        now=NOW + timedelta(minutes=1),
    )
    quotes, bars, contexts, conversions = _market(NOW + timedelta(minutes=2))
    plan = ForexV3ShadowPlanner(
        tmp_path,
        readiness=ActiveShadowReadiness(),
        ledger=ledger,
    ).plan(
        quotes=quotes,
        bars=bars,
        contexts=contexts,
        conversion_quotes=conversions,
        cycle_id="shadow-simulation-cycle-0002",
        now=NOW + timedelta(minutes=2),
    )
    rates = ForexRateBook(
        (*quotes.values(), *conversions),
        now=NOW + timedelta(minutes=2),
    )
    engine = ForexV3ShadowSimulationEngine(tmp_path, ledger=ledger)
    tampered = deepcopy(plan)
    tampered["instructions"][0]["units"] = "999999999"

    with pytest.raises(TradingValidationError, match="invalid_plan"):
        engine.apply_plan(
            tampered,
            quotes=quotes,
            rates=rates,
            cycle_id=tampered["cycle_id"],
            now=NOW + timedelta(minutes=2),
        )
    with pytest.raises(TradingValidationError, match="cycle_mismatch"):
        engine.apply_plan(
            plan,
            quotes=quotes,
            rates=rates,
            cycle_id="shadow-simulation-wrong-cycle",
            now=NOW + timedelta(minutes=2),
        )
    with pytest.raises(LiveTradingBlockedError):
        engine.submit_live_order({"pair": "EUR_USD"})
