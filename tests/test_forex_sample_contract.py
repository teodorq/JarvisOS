from copy import deepcopy
from decimal import Decimal

from app.trading.forex_risk import ForexPaperPolicy
from app.trading.forex_sample_contract import (
    CONTRACT_ID,
    build_forex_paper_sample_contract,
    is_superseded_sample_contract,
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
    execution = first["specification"]["execution_model"]
    assert execution["entry_and_signal_exit_interval_seconds"] == 900
    assert execution["position_protection_interval_seconds"] == 60
    assert execution["position_protection_source"] == "LOCAL_MT5_DEMO"
    assert execution["position_protection_actions"] == ["CLOSE_POSITION"]
    assert execution["position_check_required_before_first_full_cycle"] is True
    assert execution["position_check_required_after_runtime_gap"] is True
    assert execution["new_entries_blocked_until_position_check"] is True
    assert execution["position_recovery_replay_timeframe"] == "M1_CLOSED_BARS"
    assert execution["position_recovery_bar_limit"] == 10_080
    assert (
        execution["position_recovery_ambiguous_bar_policy"]
        == "STOP_FIRST_CONSERVATIVE"
    )
    assert execution["position_recovery_spread_policy"] == "CURRENT_MT5_SPREAD"
    assert execution["weekly_loss_window"] == "MONDAY_00_00_UTC"
    assert execution["weekly_loss_source"] == "AUDITED_CLOSED_PAPER_FILLS"
    assert execution["weekly_loss_reference"] == "INITIAL_PAPER_BALANCE"
    assert execution["weekly_loss_blocks"] == ["OPEN_LONG", "OPEN_SHORT"]
    assert execution["weekly_loss_allows"] == ["CLOSE_POSITION"]
    assert (
        first["specification"]["paper_risk_policy"]["max_weekly_loss_pct"]
        == "0.02"
    )
    assert execution["weekly_loss_window"] == "MONDAY_00_00_UTC"
    assert execution["weekly_loss_source"] == "AUDITED_CLOSED_PAPER_FILLS"
    assert execution["weekly_loss_blocks"] == ["OPEN_LONG", "OPEN_SHORT"]
    assert execution["weekly_loss_allows"] == ["CLOSE_POSITION"]
    assert (
        first["specification"]["paper_risk_policy"]["max_weekly_loss_pct"]
        == "0.02"
    )


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


def test_known_v1_contract_is_superseded_not_foreign() -> None:
    assert is_superseded_sample_contract(
        "FOREX_PAPER_V1_20260831",
        "a77112c8f1264aab11403dabf4b51b835deb96773799c8fdea1f0ace0707276a",
    ) is True
    assert is_superseded_sample_contract(
        "FOREX_PAPER_V1_20260831",
        "0" * 64,
    ) is False
    assert is_superseded_sample_contract(
        "FOREX_PAPER_V2_20260901",
        "8bc8a4e96bc663c034081593825885c7a181a07d588c0fef5fc0eb8ab193ae10",
    ) is True
    assert is_superseded_sample_contract(
        "FOREX_PAPER_V3_20260901",
        "e77c29140ba9f78f50f3ac7b7dac8f225bcdd41ea9749ef253d8dd51c7781578",
    ) is True
    assert is_superseded_sample_contract(
        "FOREX_PAPER_V4_20260902",
        "4ac87dc85189f8c0846ae3f097712e51c54f7060fefc01b2aa7c2714249b0645",
    ) is True
    assert is_superseded_sample_contract(
        "FOREX_PAPER_V4_20260902",
        "4ac87dc85189f8c0846ae3f097712e51c54f7060fefc01b2aa7c2714249b0645",
    ) is True
