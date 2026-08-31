from copy import deepcopy
from decimal import Decimal

from app.trading.forex_risk import ForexPaperPolicy
from app.trading.forex_sample_contract import (
    CONTRACT_ID,
    build_forex_paper_sample_contract,
    sample_contracts_match,
    verify_forex_paper_sample_contract,
)
from app.trading.forex_scanner import ForexScannerPolicy


def test_sample_contract_is_deterministic_and_paper_only() -> None:
    first = build_forex_paper_sample_contract()
    second = build_forex_paper_sample_contract()

    assert first == second
    assert first["contract_id"] == CONTRACT_ID
    assert len(first["fingerprint_sha256"]) == 64
    assert first["paper_only"] is True
    assert first["live_trading_enabled"] is False
    assert first["automatic_strategy_change"] is False
    assert first["automatic_live_promotion"] is False
    assert verify_forex_paper_sample_contract(first) is True
    assert sample_contracts_match(first, second) is True


def test_strategy_or_risk_change_produces_a_different_fingerprint() -> None:
    baseline = build_forex_paper_sample_contract()
    scanner_change = build_forex_paper_sample_contract(
        scanner_policy=ForexScannerPolicy(fast_window=9)
    )
    risk_change = build_forex_paper_sample_contract(
        paper_policy=ForexPaperPolicy(
            risk_per_trade_pct=Decimal("0.0020")
        )
    )

    assert not sample_contracts_match(baseline, scanner_change)
    assert not sample_contracts_match(baseline, risk_change)
    assert len({
        baseline["fingerprint_sha256"],
        scanner_change["fingerprint_sha256"],
        risk_change["fingerprint_sha256"],
    }) == 3


def test_tampering_or_live_flag_invalidates_contract() -> None:
    baseline = build_forex_paper_sample_contract()
    fingerprint_tampered = deepcopy(baseline)
    fingerprint_tampered["fingerprint_sha256"] = "0" * 64
    live_tampered = deepcopy(baseline)
    live_tampered["live_trading_enabled"] = True

    assert verify_forex_paper_sample_contract(fingerprint_tampered) is False
    assert verify_forex_paper_sample_contract(live_tampered) is False
    assert sample_contracts_match(baseline, fingerprint_tampered) is False
