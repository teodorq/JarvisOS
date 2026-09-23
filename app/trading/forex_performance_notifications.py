"""Durable owner milestone for a completed Forex PAPER trade sample."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import hashlib
import re
from typing import Any, Mapping

from app.trading.forex_performance_review import (
    verify_forex_paper_performance_review_packet,
)


_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _money(value: object) -> str | None:
    try:
        number = Decimal(str(value))
        if not number.is_finite() or abs(number) > Decimal("1000000000000"):
            return None
    except (InvalidOperation, TypeError, ValueError):
        return None
    return f"{number:.2f}"


def paper_performance_review_milestone(
    payload: object,
    *,
    completed_fingerprint: object = "",
) -> tuple[str, dict[str, str] | None]:
    """Return one safe notification when the current PAPER cohort is complete."""
    if not isinstance(payload, Mapping) or any(
        payload.get(field) is not False
        for field in ("broker_orders_sent", "live_orders_sent", "real_money_access")
    ):
        return "", None
    paper = payload.get("paper")
    paper = dict(paper) if isinstance(paper, Mapping) else {}
    account = paper.get("account")
    account = dict(account) if isinstance(account, Mapping) else {}
    performance = account.get("performance")
    performance = (
        dict(performance) if isinstance(performance, Mapping) else {}
    )
    integrity = performance.get("integrity")
    integrity = dict(integrity) if isinstance(integrity, Mapping) else {}
    account_contract = account.get("sample_contract")
    account_contract = (
        dict(account_contract) if isinstance(account_contract, Mapping) else {}
    )
    contract_review = performance.get("sample_contract_review")
    contract_review = (
        dict(contract_review) if isinstance(contract_review, Mapping) else {}
    )
    frozen = payload.get("performance_review")
    frozen = dict(frozen) if isinstance(frozen, Mapping) else {}
    frozen_snapshot = frozen.get("performance_snapshot")
    frozen_snapshot = (
        dict(frozen_snapshot) if isinstance(frozen_snapshot, Mapping) else {}
    )
    current_required = performance.get("minimum_closed_trades_for_review")
    current_count = performance.get("valid_closed_trade_count")
    required = frozen.get("minimum_closed_trades_for_review")
    count = frozen.get("valid_closed_trade_count")
    contract_id = str(account_contract.get("contract_id", ""))
    contract_fingerprint = str(account_contract.get("fingerprint_sha256", ""))
    net_pnl = _money(frozen_snapshot.get("net_realized_pnl_pln"))
    drawdown = _money(
        frozen_snapshot.get("maximum_closed_trade_drawdown_pln")
    )
    if (
        payload.get("status") != "PAPER_CYCLE_COMPLETED"
        or paper.get("status") != "CYCLE_COMPLETED"
        or paper.get("mode") != "FOREX_PAPER_ONLY"
        or paper.get("live_orders_sent") is not False
        or paper.get("network_access") is not False
        or not verify_forex_paper_performance_review_packet(frozen)
        or account.get("status") != "READY"
        or account.get("mode") != "FOREX_PAPER_ONLY"
        or account_contract.get("paper_only") is not True
        or account_contract.get("live_trading_enabled") is not False
        or not contract_id
        or not _SHA256.fullmatch(contract_fingerprint)
        or performance.get("status") != "READY_FOR_MANUAL_REVIEW"
        or performance.get("mode") != "FOREX_PAPER_PERFORMANCE_READ_ONLY"
        or performance.get("metric_scope") != "CURRENT_SAMPLE_CONTRACT"
        or type(current_required) is not int
        or current_required != required
        or type(current_count) is not int
        or current_count < count
        or performance.get("remaining_closed_trades_for_review") != 0
        or performance.get("sample_size_sufficient_for_review") is not True
        or performance.get("performance_validated") is not False
        or performance.get("automatic_paper_strategy_change") is not False
        or performance.get("live_promotion_ready") is not False
        or performance.get("automatic_live_promotion") is not False
        or integrity.get("evidence_valid") is not True
        or integrity.get("audit_chain_valid") is not True
        or integrity.get("execution_audit_matches_ledger") is not True
        or integrity.get("balance_reconciled") is not True
        or integrity.get("invalid_closed_fill_count") != 0
        or contract_review.get("status") != "TRACKING_CURRENT_CONTRACT"
        or contract_review.get("mode")
        != "FOREX_PAPER_SAMPLE_CONTRACT_READ_ONLY"
        or contract_review.get("contract_tracking_enabled") is not True
        or contract_review.get("expected_contract_id") != contract_id
        or contract_review.get("expected_fingerprint_sha256")
        != contract_fingerprint
        or contract_review.get("current_contract_closed_trade_count")
        != current_count
        or contract_review.get("foreign_contract_closed_trade_count") != 0
        or contract_review.get("sample_contract_consistent") is not True
        or contract_review.get("automatic_sample_merge") is not False
        or contract_review.get("automatic_strategy_change") is not False
        or contract_review.get("live_promotion_ready") is not False
        or frozen.get("sample_contract_id") != contract_id
        or frozen.get("sample_contract_fingerprint_sha256")
        != contract_fingerprint
        or net_pnl is None
        or drawdown is None
    ):
        return "", None
    identity = f"{contract_id}|{contract_fingerprint}|{required}"
    fingerprint = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    if fingerprint == str(completed_fingerprint):
        return fingerprint, None
    occurred_at = " ".join(str(payload.get("observed_at", "")).split())[:64]
    return fingerprint, {
        "kind": "FOREX_PAPER_SAMPLE_REVIEW_READY",
        "state": "important",
        "message": (
            f"Forex PAPER: zweryfikowana próbka osiągnęła {count}/{required} "
            f"zamkniętych transakcji. Wynik próbki: {net_pnl} PLN; maksymalne "
            f"obsunięcie zamkniętych transakcji: {drawdown} PLN. Dane są gotowe "
            "wyłącznie do ręcznego przeglądu; nie potwierdzają skuteczności, "
            "nie zmieniają strategii i nie włączają LIVE."
        ),
        "occurred_at": occurred_at,
        "token": f"forex-paper-performance-review:{fingerprint}",
    }


__all__ = ["paper_performance_review_milestone"]
