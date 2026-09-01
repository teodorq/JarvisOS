from __future__ import annotations

from decimal import Decimal

import pytest

from app.trading.forex_paper_performance import (
    ForexPaperPerformancePolicy,
    build_forex_paper_performance_review,
)
from app.trading.forex_sample_contract import build_forex_paper_sample_contract
from app.trading.models import TradingValidationError


def _fill(pnl: object, index: int) -> dict[str, object]:
    return {
        "fill_id": f"paper-close-{index}",
        "action": "CLOSE_LONG",
        "pair": "EUR_USD",
        "realized_pnl_pln": pnl,
    }


def _review(values: list[object], *, audit_matches: bool = True) -> dict:
    net = sum((Decimal(str(value)) for value in values), Decimal("0"))
    return build_forex_paper_performance_review(
        [_fill(value, index) for index, value in enumerate(values)],
        initial_balance_pln="100000",
        current_balance_pln=str(Decimal("100000") + net),
        audit_chain_valid=True,
        execution_audit_matches_ledger=audit_matches,
    )


def test_empty_review_is_valid_but_requires_a_real_sample() -> None:
    review = _review([])

    assert review["status"] == "COLLECTING_PAPER_SAMPLE"
    assert review["valid_closed_trade_count"] == 0
    assert review["remaining_closed_trades_for_review"] == 20
    assert review["sample_progress_pct"] == "0.00"
    assert review["profit_factor"] is None
    assert review["profit_factor_status"] == "NO_CLOSED_TRADES"
    assert review["integrity"]["evidence_valid"] is True
    assert review["performance_validated"] is False
    assert review["live_promotion_ready"] is False


def test_review_calculates_profit_factor_drawdown_and_loss_streak() -> None:
    review = _review(["100", "-40", "-30", "10", "-50"])

    assert review["valid_closed_trade_count"] == 5
    assert review["winning_trade_count"] == 2
    assert review["losing_trade_count"] == 3
    assert review["win_rate_pct"] == "40.00"
    assert review["net_realized_pnl_pln"] == "-10.00"
    assert review["gross_profit_pln"] == "110.00"
    assert review["gross_loss_abs_pln"] == "120.00"
    assert review["average_trade_pnl_pln"] == "-2.00"
    assert review["average_win_pnl_pln"] == "55.00"
    assert review["average_loss_pnl_pln"] == "-40.00"
    assert review["profit_factor"] == "0.9167"
    assert review["maximum_closed_trade_drawdown_pln"] == "110.00"
    assert review["maximum_closed_trade_drawdown_pct"] == "0.11"
    assert review["maximum_consecutive_losses"] == 2
    assert review["current_consecutive_losses"] == 1
    assert review["integrity"]["balance_reconciled"] is True
    eur = review["pair_breakdown"]["EUR_USD"]
    assert eur["closed_trade_count"] == 5
    assert eur["net_realized_pnl_pln"] == "-10.00"
    assert eur["average_trade_pnl_pln"] == "-2.00"
    assert eur["profit_factor"] == "0.9167"
    assert eur["maximum_consecutive_losses"] == 2
    assert eur["review_status"] == "COLLECTING_PAIR_SAMPLE"
    assert eur["sample_progress_pct"] == "25.00"
    assert eur["remaining_closed_trades_for_review"] == 15
    assert review["pair_breakdown"]["GBP_USD"]["closed_trade_count"] == 0
    assert review["pair_breakdown"]["GBP_USD"]["review_status"] == "NO_CLOSED_TRADES"
    assert review["pair_breakdown"]["GBP_USD"]["performance_validated"] is False
    assert review["pair_review"]["ready_pair_count"] == 0
    assert review["pair_review"]["collecting_pairs"] == ["EUR_USD"]
    assert review["pair_review"]["unobserved_pair_count"] == 6
    assert review["pair_review"]["automatic_pair_selection"] is False


def test_full_sample_only_opens_manual_review_not_live_promotion() -> None:
    review = _review(["1"] * 20)

    assert review["status"] == "READY_FOR_MANUAL_REVIEW"
    assert review["sample_size_sufficient_for_review"] is True
    assert review["remaining_closed_trades_for_review"] == 0
    assert review["profit_factor"] is None
    assert review["profit_factor_status"] == "NO_GROSS_LOSS"
    assert review["performance_validated"] is False
    assert review["automatic_paper_strategy_change"] is False
    assert review["live_promotion_ready"] is False
    assert review["automatic_live_promotion"] is False
    assert review["pair_breakdown"]["EUR_USD"]["review_status"] == (
        "READY_FOR_MANUAL_REVIEW"
    )
    assert review["pair_review"]["ready_pairs"] == ["EUR_USD"]
    assert review["pair_review"]["all_pairs_ready_for_manual_review"] is False


def test_invalid_fill_or_audit_mismatch_blocks_evidence() -> None:
    invalid = build_forex_paper_performance_review(
        [_fill("NaN", 1)],
        initial_balance_pln="100000",
        current_balance_pln="100000",
        audit_chain_valid=True,
        execution_audit_matches_ledger=True,
    )
    mismatch = _review(["1"], audit_matches=False)

    assert invalid["status"] == "BLOCKED_INVALID_EVIDENCE"
    assert invalid["integrity"]["invalid_closed_fill_count"] == 1
    assert invalid["integrity"]["evidence_valid"] is False
    assert mismatch["status"] == "BLOCKED_INVALID_EVIDENCE"
    assert mismatch["integrity"]["execution_audit_matches_ledger"] is False
    assert all(
        item["review_status"] == "BLOCKED_INVALID_EVIDENCE"
        for item in mismatch["pair_breakdown"].values()
    )


def test_balance_that_does_not_reconcile_blocks_evidence() -> None:
    review = build_forex_paper_performance_review(
        [_fill("10", 1)],
        initial_balance_pln="100000",
        current_balance_pln="100000",
        audit_chain_valid=True,
        execution_audit_matches_ledger=True,
    )

    assert review["status"] == "BLOCKED_INVALID_EVIDENCE"
    assert review["integrity"]["balance_reconciled"] is False
    assert review["integrity"]["balance_reconciliation_delta_pln"] == "-10.00"
    assert review["integrity"]["evidence_valid"] is False


def test_policy_rejects_unsafe_sample_threshold() -> None:
    with pytest.raises(TradingValidationError):
        ForexPaperPerformancePolicy(minimum_closed_trades_for_review=0)


def test_contract_tracking_excludes_legacy_and_foreign_fills_from_sample() -> None:
    expected = {
        "contract_id": "FOREX_PAPER_V1_20260831",
        "fingerprint_sha256": "a" * 64,
    }
    current = _fill("5", 1)
    current["sample_contract_id"] = expected["contract_id"]
    current["sample_contract_fingerprint_sha256"] = expected[
        "fingerprint_sha256"
    ]
    legacy = _fill("10", 2)
    foreign = _fill("-2", 3)
    foreign["sample_contract_id"] = "FOREX_PAPER_OTHER"
    foreign["sample_contract_fingerprint_sha256"] = "b" * 64

    review = build_forex_paper_performance_review(
        [legacy, current, foreign],
        initial_balance_pln="100000",
        current_balance_pln="100013",
        audit_chain_valid=True,
        execution_audit_matches_ledger=True,
        expected_sample_contract=expected,
    )

    assert review["valid_closed_trade_count"] == 1
    assert review["all_time_closed_trade_count"] == 3
    assert review["sample_progress_pct"] == "5.00"
    assert review["winning_trade_count"] == 1
    assert review["losing_trade_count"] == 0
    assert review["net_realized_pnl_pln"] == "5.00"
    assert review["average_trade_pnl_pln"] == "5.00"
    assert review["profit_factor"] is None
    assert review["all_time_summary"]["closed_trade_count"] == 3
    assert review["all_time_summary"]["net_realized_pnl_pln"] == "13.00"
    contract = review["sample_contract_review"]
    assert contract["current_contract_closed_trade_count"] == 1
    assert contract["legacy_unversioned_closed_trade_count"] == 1
    assert contract["foreign_contract_closed_trade_count"] == 1
    assert contract["sample_contract_consistent"] is False
    assert review["pair_breakdown"]["EUR_USD"][
        "sample_contract_closed_trade_count"
    ] == 1
    eur = review["pair_breakdown"]["EUR_USD"]
    assert eur["closed_trade_count"] == 1
    assert eur["all_time_closed_trade_count"] == 3
    assert eur["net_realized_pnl_pln"] == "5.00"
    assert eur["all_time_net_realized_pnl_pln"] == "13.00"


def test_known_predecessor_is_excluded_without_marking_sample_inconsistent() -> None:
    expected = build_forex_paper_sample_contract()
    predecessor = _fill("7", 1)
    predecessor["sample_contract_id"] = "FOREX_PAPER_V1_20260831"
    predecessor["sample_contract_fingerprint_sha256"] = (
        "a77112c8f1264aab11403dabf4b51b835deb96773799c8fdea1f0ace0707276a"
    )

    review = build_forex_paper_performance_review(
        [predecessor],
        initial_balance_pln="100000",
        current_balance_pln="100007",
        audit_chain_valid=True,
        execution_audit_matches_ledger=True,
        expected_sample_contract=expected,
    )

    contract = review["sample_contract_review"]
    assert review["valid_closed_trade_count"] == 0
    assert contract["superseded_contract_closed_trade_count"] == 1
    assert contract["foreign_contract_closed_trade_count"] == 0
    assert contract["sample_contract_consistent"] is True
