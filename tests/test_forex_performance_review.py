from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from app.trading.forex_executor import ForexPaperExecutionEngine
from app.trading.forex_ledger import ForexPaperLedger
from app.trading.forex_performance_review import (
    ForexPaperPerformanceReviewPacket,
    verify_forex_paper_performance_review_lineage,
    verify_forex_paper_performance_review_packet,
)
from app.trading.forex_sample_contract import build_forex_paper_sample_contract


UTC = timezone.utc
NOW = datetime(2026, 9, 1, 10, 0, tzinfo=UTC)


def _append_closed_trade(
    ledger: ForexPaperLedger,
    contract: dict,
    index: int,
    *,
    record_risk: bool = True,
) -> None:
    filled_at = NOW + timedelta(minutes=15 * index)
    pnl = Decimal("2.00") if index % 2 else Decimal("-1.00")
    fill = {
        "fill_id": f"paper-performance-close-{index:03d}",
        "action": "CLOSE_LONG",
        "pair": "EUR_USD",
        "realized_pnl_pln": str(pnl),
        "filled_at": filled_at.isoformat(),
        "opened_at": (filled_at - timedelta(minutes=30)).isoformat(),
        "sample_contract_id": contract["contract_id"],
        "sample_contract_fingerprint_sha256": contract[
            "fingerprint_sha256"
        ],
    }
    if record_risk:
        fill["initial_risk_pln"] = "2.00"

    def operation(state: dict) -> None:
        state["fills"] = list(state.get("fills", [])) + [fill]
        state["balance_pln"] = str(
            Decimal(str(state["balance_pln"])) + pnl
        )
        ledger.append_event(
            state,
            "FOREX_PAPER_CYCLE",
            {"cycle_id": f"packet-cycle-{index:03d}", "executions": [fill]},
            created_at=filled_at,
        )

    ledger.transaction(operation)


def _account(root: Path, contract: dict) -> dict:
    return ForexPaperExecutionEngine(
        root,
        sample_contract=contract,
    ).status(now=NOW + timedelta(days=1))


def test_packet_waits_without_persisting_an_incomplete_sample(
    tmp_path: Path,
) -> None:
    ledger = ForexPaperLedger(tmp_path)
    contract = build_forex_paper_sample_contract()
    for index in range(19):
        _append_closed_trade(ledger, contract, index)
    store = ForexPaperPerformanceReviewPacket(tmp_path)

    packet = store.refresh(_account(tmp_path, contract), generated_at=NOW)

    assert packet["status"] == "WAITING_FOR_PAPER_SAMPLE"
    assert packet["valid_closed_trade_count"] == 19
    assert packet["remaining_closed_trades_for_review"] == 1
    assert packet["packet_persisted"] is False
    assert not store.path.exists()


def test_first_complete_sample_is_frozen_and_survives_later_trades(
    tmp_path: Path,
) -> None:
    ledger = ForexPaperLedger(tmp_path)
    contract = build_forex_paper_sample_contract()
    for index in range(20):
        _append_closed_trade(ledger, contract, index)
    store = ForexPaperPerformanceReviewPacket(tmp_path)
    first_account = _account(tmp_path, contract)

    frozen = store.refresh(first_account, generated_at=NOW)

    assert frozen["status"] == "READY_FOR_OWNER_REVIEW"
    assert frozen["schema_version"] == 3
    assert frozen["valid_closed_trade_count"] == 20
    assert frozen["packet_persisted"] is True
    assert frozen["review_snapshot_frozen"] is True
    assert frozen["risk_snapshot"] == {
        "status": "COMPLETE",
        "closed_trade_count": 20,
        "risk_observed_trade_count": 20,
        "risk_missing_trade_count": 0,
        "risk_coverage_pct": "100.00",
        "risk_coverage_complete": True,
        "net_r_multiple": "5.0000",
        "average_r_multiple": "0.2500",
        "median_r_multiple": "0.2500",
        "best_r_multiple": "1.0000",
        "worst_r_multiple": "-0.5000",
        "winning_r_trade_count": 10,
        "losing_r_trade_count": 10,
        "breakeven_r_trade_count": 0,
        "maximum_observed_drawdown_r": "0.5000",
        "maximum_observed_consecutive_losses": 1,
        "current_observed_consecutive_losses": 0,
    }
    assert verify_forex_paper_performance_review_packet(frozen)
    assert verify_forex_paper_performance_review_lineage(
        first_account, ledger.snapshot(), frozen
    )

    _append_closed_trade(ledger, contract, 20)
    later_account = _account(tmp_path, contract)
    reviewed = store.review(later_account, generated_at=NOW + timedelta(days=1))

    assert later_account["performance"]["valid_closed_trade_count"] == 21
    assert reviewed == frozen
    assert reviewed["valid_closed_trade_count"] == 20
    assert verify_forex_paper_performance_review_lineage(
        later_account, ledger.snapshot(), reviewed
    )


def test_complete_sample_freezes_partial_legacy_risk_coverage(
    tmp_path: Path,
) -> None:
    ledger = ForexPaperLedger(tmp_path)
    contract = build_forex_paper_sample_contract()
    for index in range(20):
        _append_closed_trade(
            ledger,
            contract,
            index,
            record_risk=index >= 5,
        )
    store = ForexPaperPerformanceReviewPacket(tmp_path)

    frozen = store.refresh(_account(tmp_path, contract), generated_at=NOW)

    assert frozen["status"] == "READY_FOR_OWNER_REVIEW"
    assert frozen["risk_snapshot"] == {
        "status": "PARTIAL",
        "closed_trade_count": 20,
        "risk_observed_trade_count": 15,
        "risk_missing_trade_count": 5,
        "risk_coverage_pct": "75.00",
        "risk_coverage_complete": False,
        "net_r_multiple": "4.5000",
        "average_r_multiple": "0.3000",
        "median_r_multiple": "1.0000",
        "best_r_multiple": "1.0000",
        "worst_r_multiple": "-0.5000",
        "winning_r_trade_count": 8,
        "losing_r_trade_count": 7,
        "breakeven_r_trade_count": 0,
        "maximum_observed_drawdown_r": "0.5000",
        "maximum_observed_consecutive_losses": 1,
        "current_observed_consecutive_losses": 0,
    }
    assert verify_forex_paper_performance_review_packet(frozen)


def test_tampered_ledger_blocks_saved_packet_lineage(tmp_path: Path) -> None:
    ledger = ForexPaperLedger(tmp_path)
    contract = build_forex_paper_sample_contract()
    for index in range(20):
        _append_closed_trade(ledger, contract, index)
    store = ForexPaperPerformanceReviewPacket(tmp_path)
    frozen = store.refresh(_account(tmp_path, contract), generated_at=NOW)

    def tamper(state: dict) -> None:
        state["fills"][0]["realized_pnl_pln"] = "999.00"

    ledger.transaction(tamper)
    blocked = store.review(_account(tmp_path, contract), generated_at=NOW)

    assert verify_forex_paper_performance_review_packet(frozen)
    assert blocked["status"] == "BLOCKED_INVALID_PAPER_PERFORMANCE_EVIDENCE"
    assert blocked["packet_persisted"] is False


def test_tampered_packet_content_hash_is_rejected(tmp_path: Path) -> None:
    ledger = ForexPaperLedger(tmp_path)
    contract = build_forex_paper_sample_contract()
    for index in range(20):
        _append_closed_trade(ledger, contract, index)
    packet = ForexPaperPerformanceReviewPacket(tmp_path).refresh(
        _account(tmp_path, contract), generated_at=NOW
    )

    packet["performance_snapshot"]["net_realized_pnl_pln"] = "999.00"

    assert not verify_forex_paper_performance_review_packet(packet)


def test_risk_snapshot_must_match_the_audited_ledger(tmp_path: Path) -> None:
    ledger = ForexPaperLedger(tmp_path)
    contract = build_forex_paper_sample_contract()
    for index in range(20):
        _append_closed_trade(ledger, contract, index)
    account = _account(tmp_path, contract)
    account["performance"]["risk_diagnostics"]["average_r_multiple"] = "9.0000"

    packet = ForexPaperPerformanceReviewPacket(tmp_path).refresh(
        account,
        generated_at=NOW,
    )

    assert packet["status"] == "BLOCKED_INVALID_PAPER_PERFORMANCE_EVIDENCE"
    assert packet["packet_persisted"] is False
    assert not ForexPaperPerformanceReviewPacket(tmp_path).path.exists()


def test_tampered_risk_snapshot_is_rejected_even_with_new_hash_absent(
    tmp_path: Path,
) -> None:
    ledger = ForexPaperLedger(tmp_path)
    contract = build_forex_paper_sample_contract()
    for index in range(20):
        _append_closed_trade(ledger, contract, index)
    packet = ForexPaperPerformanceReviewPacket(tmp_path).refresh(
        _account(tmp_path, contract), generated_at=NOW
    )

    packet["risk_snapshot"]["risk_observed_trade_count"] = 19

    assert not verify_forex_paper_performance_review_packet(packet)
