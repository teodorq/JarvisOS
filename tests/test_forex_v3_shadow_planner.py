from __future__ import annotations

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
from app.trading.forex_executor import ForexPaperExecutionEngine
from app.trading.forex_risk import ForexRateBook
from app.trading.forex_v3_shadow_ledger import ForexV3ShadowLedger
from app.trading.forex_v3_shadow_plan_journal import (
    ForexV3ShadowPlanJournal,
)
from app.trading.forex_v3_shadow_plan_observer import (
    ForexV3ShadowPlanObserver,
)
from app.trading.forex_v3_shadow_planner import ForexV3ShadowPlanner
from app.trading.forex_v3_shadow_planner import verify_forex_v3_shadow_plan
from app.trading.models import TradingValidationError
from app.trading.paper_broker import LiveTradingBlockedError


NOW = datetime(2026, 10, 2, 12, tzinfo=timezone.utc)
BASE = {
    "EUR_USD": Decimal("1.1000"),
    "GBP_USD": Decimal("1.2800"),
    "USD_JPY": Decimal("150.00"),
    "USD_CHF": Decimal("0.9000"),
    "AUD_USD": Decimal("0.6600"),
    "USD_CAD": Decimal("1.3500"),
    "NZD_USD": Decimal("0.6100"),
}


class InitializedReadiness:
    @staticmethod
    def status() -> dict:
        return {
            "status": "SHADOW_INITIALIZED_INACTIVE",
            "shadow_ledger_initialized": True,
            "shadow_execution_enabled": False,
        }


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


def _initialized_ledger(tmp_path) -> ForexV3ShadowLedger:
    ledger = ForexV3ShadowLedger(tmp_path)

    def initialize(state: dict) -> None:
        state["initialization"] = {
            "status": "INITIALIZED_SHADOW_INACTIVE",
            "initialized_at": NOW.isoformat(),
            "forward_evidence_content_sha256": "a" * 64,
            "source_head_hash": "b" * 64,
            "source_cutoff_sequence": 20,
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


def test_planner_stays_blocked_and_does_not_create_shadow_ledger(tmp_path) -> None:
    planner = ForexV3ShadowPlanner(tmp_path)

    result = planner.plan(
        quotes={},
        bars={},
        contexts={},
        conversion_quotes=(),
        cycle_id="shadow-plan-0001",
        now=NOW,
    )

    assert result["status"] == "BLOCKED_SHADOW_PLAN"
    assert result["instructions"] == []
    assert result["executable"] is False
    assert result["shadow_execution_enabled"] is False
    assert not planner.ledger.path.exists()


def test_initialized_planner_builds_signed_non_executable_v3_plan(tmp_path) -> None:
    ledger = _initialized_ledger(tmp_path)
    planner = ForexV3ShadowPlanner(
        tmp_path,
        readiness=InitializedReadiness(),
        ledger=ledger,
    )
    before = ledger.snapshot()
    quotes, bars, contexts, conversions = _market()

    result = planner.plan(
        quotes=quotes,
        bars=bars,
        contexts=contexts,
        conversion_quotes=conversions,
        cycle_id="shadow-plan-0002",
        now=NOW,
    )
    after = ledger.snapshot()

    assert result["status"] == "SHADOW_PLAN_COMPUTED"
    assert result["decision_status"] == "ENTRIES_READY"
    assert result["mode"] == "FOREX_V3_SHADOW_PLAN_ONLY"
    assert result["candidate_id"] == "FOREX_STRENGTH_V3_20260929"
    assert result["instructions"][0]["action"] == "OPEN_LONG"
    assert result["instructions"][0]["pair"] == "EUR_USD"
    assert result["instructions"][0]["executable"] is False
    assert result["executable"] is False
    assert result["paper_orders_sent"] is False
    assert result["live_orders_sent"] is False
    assert result["network_access"] is False
    assert len(result["plan_sha256"]) == 64
    assert result["shadow_ledger_audit_head"] == before["audit"][-1][
        "event_hash"
    ]
    assert after == before
    assert not (tmp_path / "data/trading/forex_paper_ledger.json").exists()

    rates = ForexRateBook(
        (*quotes.values(), *conversions),
        now=NOW,
    )
    base_executor = ForexPaperExecutionEngine(tmp_path)
    with pytest.raises(TradingValidationError, match="paper_mode_required"):
        base_executor.apply_plan(
            result,
            quotes=quotes,
            rates=rates,
            cycle_id="base-rejects-shadow-plan",
            now=NOW,
        )
    assert not base_executor.ledger.path.exists()


def test_shadow_planner_live_submission_is_impossible() -> None:
    with pytest.raises(LiveTradingBlockedError):
        ForexV3ShadowPlanner.submit_live_order({"pair": "EUR_USD"})


def test_plan_journal_records_once_without_touching_shadow_positions(
    tmp_path,
) -> None:
    ledger = _initialized_ledger(tmp_path)
    planner = ForexV3ShadowPlanner(
        tmp_path,
        readiness=InitializedReadiness(),
        ledger=ledger,
    )
    quotes, bars, contexts, conversions = _market()
    plan = planner.plan(
        quotes=quotes,
        bars=bars,
        contexts=contexts,
        conversion_quotes=conversions,
        cycle_id="shadow-plan-journal-0001",
        now=NOW,
    )
    before = ledger.snapshot()
    journal = ForexV3ShadowPlanJournal(tmp_path)

    first = journal.record(plan)
    duplicate = journal.record(plan)
    state = journal.snapshot()
    after = ledger.snapshot()

    assert verify_forex_v3_shadow_plan(plan) is True
    assert first == {"status": "SHADOW_PLAN_RECORDED", "plans_recorded": 1}
    assert duplicate == {"status": "DUPLICATE_SHADOW_PLAN", "plans_recorded": 0}
    assert len(state["plans"]) == 1
    assert state["plans"][0]["instruction_count"] == 1
    assert ForexV3ShadowPlanJournal.verify(state) is True
    assert after == before
    assert after["positions"] == {}
    assert after["fills"] == []
    summary = journal.summary()
    assert summary["status"] == "COLLECTING_SHADOW_PLANS"
    assert summary["audit_chain_valid"] is True
    assert summary["plan_count"] == 1
    assert summary["minimum_plan_count"] == 20
    assert summary["remaining_plan_count"] == 19
    assert summary["market_day_count"] == 1
    assert summary["minimum_market_day_count"] == 3
    assert summary["remaining_market_day_count"] == 2
    assert summary["plan_sample_complete"] is False
    assert summary["performance_validated"] is False
    assert summary["simulation_activation_ready"] is False
    assert summary["entry_plan_count"] == 1
    assert summary["instruction_count"] == 1
    assert summary["latest_cycle_id"] == "shadow-plan-journal-0001"
    assert summary["shadow_execution_enabled"] is False


def test_plan_journal_rejects_tampering_without_creating_file(tmp_path) -> None:
    ledger = _initialized_ledger(tmp_path)
    planner = ForexV3ShadowPlanner(
        tmp_path,
        readiness=InitializedReadiness(),
        ledger=ledger,
    )
    quotes, bars, contexts, conversions = _market()
    plan = planner.plan(
        quotes=quotes,
        bars=bars,
        contexts=contexts,
        conversion_quotes=conversions,
        cycle_id="shadow-plan-journal-0002",
        now=NOW,
    )
    plan["instructions"][0]["executable"] = True
    journal = ForexV3ShadowPlanJournal(tmp_path)

    result = journal.record(plan)

    assert verify_forex_v3_shadow_plan(plan) is False
    assert result == {"status": "INVALID_SHADOW_PLAN", "plans_recorded": 0}
    assert not journal.path.exists()


def test_empty_plan_journal_summary_does_not_create_file(tmp_path) -> None:
    journal = ForexV3ShadowPlanJournal(tmp_path)

    summary = journal.summary()

    assert summary["status"] == "WAITING_FOR_FIRST_SHADOW_PLAN"
    assert summary["journal_initialized"] is False
    assert summary["audit_chain_valid"] is True
    assert summary["plan_count"] == 0
    assert summary["remaining_plan_count"] == 20
    assert summary["market_day_count"] == 0
    assert summary["remaining_market_day_count"] == 3
    assert summary["plan_sample_complete"] is False
    assert summary["instruction_count"] == 0
    assert summary["shadow_execution_enabled"] is False
    assert not journal.path.exists()


def test_plan_journal_requires_twenty_plans_across_three_days(tmp_path) -> None:
    ledger = _initialized_ledger(tmp_path)
    planner = ForexV3ShadowPlanner(
        tmp_path,
        readiness=InitializedReadiness(),
        ledger=ledger,
    )
    journal = ForexV3ShadowPlanJournal(tmp_path)
    before = ledger.snapshot()

    for index in range(20):
        assessed_at = NOW + timedelta(
            days=index // 7,
            minutes=15 * (index % 7),
        )
        quotes, bars, contexts, conversions = _market(assessed_at)
        plan = planner.plan(
            quotes=quotes,
            bars=bars,
            contexts=contexts,
            conversion_quotes=conversions,
            cycle_id=f"shadow-plan-sample-{index:04d}",
            now=assessed_at,
        )
        assert journal.record(plan)["status"] == "SHADOW_PLAN_RECORDED"

    summary = journal.summary()

    assert summary["status"] == "SHADOW_PLAN_SAMPLE_COMPLETE"
    assert summary["plan_count"] == 20
    assert summary["remaining_plan_count"] == 0
    assert summary["market_day_count"] == 3
    assert summary["remaining_market_day_count"] == 0
    assert summary["plan_sample_complete"] is True
    assert summary["performance_validated"] is False
    assert summary["simulation_activation_ready"] is False
    assert summary["shadow_execution_enabled"] is False
    assert ledger.snapshot() == before


def test_corrupted_existing_plan_journal_is_preserved_and_blocks(tmp_path) -> None:
    ledger = _initialized_ledger(tmp_path)
    planner = ForexV3ShadowPlanner(
        tmp_path,
        readiness=InitializedReadiness(),
        ledger=ledger,
    )
    quotes, bars, contexts, conversions = _market()
    plan = planner.plan(
        quotes=quotes,
        bars=bars,
        contexts=contexts,
        conversion_quotes=conversions,
        cycle_id="shadow-plan-journal-0003",
        now=NOW,
    )
    journal = ForexV3ShadowPlanJournal(tmp_path)
    journal.path.parent.mkdir(parents=True, exist_ok=True)
    journal.path.write_text("{broken", encoding="utf-8")

    result = journal.record(plan)

    assert result == {
        "status": "BLOCKED_SHADOW_PLAN_JOURNAL_INVALID",
        "plans_recorded": 0,
    }
    assert journal.path.read_text(encoding="utf-8") == "{broken"
    assert journal.snapshot()["mode"] == "INVALID"
    assert journal.summary()["status"] == (
        "BLOCKED_SHADOW_PLAN_JOURNAL_INVALID"
    )


def test_plan_observer_waits_without_creating_any_shadow_file(tmp_path) -> None:
    observer = ForexV3ShadowPlanObserver(tmp_path)

    result = observer.observe(
        quotes={},
        bars={},
        contexts={},
        conversion_quotes=(),
        cycle_id="observer-wait-0001",
        now=NOW,
    )

    assert result["status"] == "SHADOW_PLAN_OBSERVATION_WAITING"
    assert result["journal_status"] == "NOT_WRITTEN"
    assert result["shadow_execution_enabled"] is False
    assert result["paper_orders_sent"] is False
    assert result["live_orders_sent"] is False
    assert not observer.planner.ledger.path.exists()
    assert not observer.journal.path.exists()


def test_plan_observer_archives_plan_but_never_executes_it(tmp_path) -> None:
    ledger = _initialized_ledger(tmp_path)
    planner = ForexV3ShadowPlanner(
        tmp_path,
        readiness=InitializedReadiness(),
        ledger=ledger,
    )
    journal = ForexV3ShadowPlanJournal(tmp_path)
    observer = ForexV3ShadowPlanObserver(
        tmp_path,
        planner=planner,
        journal=journal,
    )
    quotes, bars, contexts, conversions = _market()
    before = ledger.snapshot()

    result = observer.observe(
        quotes=quotes,
        bars=bars,
        contexts=contexts,
        conversion_quotes=conversions,
        cycle_id="observer-record-0001",
        now=NOW,
    )
    repeated = observer.observe(
        quotes=quotes,
        bars=bars,
        contexts=contexts,
        conversion_quotes=conversions,
        cycle_id="observer-record-0001",
        now=NOW,
    )

    assert result["status"] == "SHADOW_PLAN_OBSERVED"
    assert result["journal_status"] == "SHADOW_PLAN_RECORDED"
    assert repeated["status"] == "SHADOW_PLAN_ALREADY_OBSERVED"
    assert result["plan"]["executable"] is False
    assert result["broker_orders_sent"] is False
    assert result["live_orders_sent"] is False
    assert ledger.snapshot() == before
    assert len(journal.snapshot()["plans"]) == 1
