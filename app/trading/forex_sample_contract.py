"""Deterministic contract for one comparable Forex PAPER sample cohort."""

from __future__ import annotations

from dataclasses import fields, is_dataclass
from decimal import Decimal
import hashlib
import hmac
import json
from typing import Any, Iterable, Mapping

from app.trading.forex_coordinator import ForexPaperCoordinator
from app.trading.forex_models import ForexPair, MAJOR_FOREX_PAIRS
from app.trading.forex_risk import ForexPaperPolicy
from app.trading.forex_scanner import ForexScannerPolicy


CONTRACT_ID = "FOREX_PAPER_V2_20260901"
SUPERSEDED_CONTRACT_FINGERPRINTS = {
    "FOREX_PAPER_V1_20260831": (
        "a77112c8f1264aab11403dabf4b51b835deb96773799c8fdea1f0ace0707276a"
    ),
}


def _value(value: object) -> object:
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (str, int, bool)) or value is None:
        return value
    raise TypeError("forex_sample_contract: unsupported_policy_value")


def _policy_values(value: object) -> dict[str, object]:
    if not is_dataclass(value):
        raise TypeError("forex_sample_contract: dataclass_policy_required")
    return {
        item.name: _value(getattr(value, item.name))
        for item in fields(value)
    }


def _fingerprint(value: Mapping[str, Any]) -> str:
    encoded = json.dumps(
        dict(value),
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def build_forex_paper_sample_contract(
    *,
    scanner_policy: ForexScannerPolicy | None = None,
    paper_policy: ForexPaperPolicy | None = None,
    universe: Iterable[ForexPair] = MAJOR_FOREX_PAIRS,
) -> dict[str, Any]:
    scanner = scanner_policy or ForexScannerPolicy()
    paper = paper_policy or ForexPaperPolicy()
    pairs = tuple(pair.symbol for pair in universe)
    if pairs != tuple(pair.symbol for pair in MAJOR_FOREX_PAIRS):
        raise ValueError("forex_sample_contract: unexpected_universe")
    contract: dict[str, Any] = {
        "schema_version": 1,
        "contract_id": CONTRACT_ID,
        "mode": "FOREX_PAPER_SAMPLE_CONTRACT",
        "specification": {
            "strategy_id": "M15_SMA_CROSSOVER_V1",
            "timeframe": "M15_CLOSED_BARS",
            "universe": list(pairs),
            "scanner_policy": _policy_values(scanner),
            "paper_risk_policy": _policy_values(paper),
            "coordinator": {
                "minimum_stop_pips": str(
                    ForexPaperCoordinator.MINIMUM_STOP_PIPS
                ),
                "maximum_stop_pips": str(
                    ForexPaperCoordinator.MAXIMUM_STOP_PIPS
                ),
            },
            "execution_model": {
                "open_long_price": "ASK",
                "open_short_price": "BID",
                "close_long_price": "BID",
                "close_short_price": "ASK",
                "commission_model": "NONE",
                "swap_model": "NONE",
                "extra_slippage_model": "NONE",
                "entry_and_signal_exit_interval_seconds": 900,
                "position_protection_interval_seconds": 60,
                "position_protection_source": "LOCAL_MT5_DEMO",
                "position_protection_actions": ["CLOSE_POSITION"],
            },
        },
        "paper_only": True,
        "live_trading_enabled": False,
        "automatic_strategy_change": False,
        "automatic_live_promotion": False,
    }
    contract["fingerprint_sha256"] = _fingerprint(contract)
    return contract


def verify_forex_paper_sample_contract(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    contract = dict(value)
    fingerprint = str(contract.pop("fingerprint_sha256", ""))
    if len(fingerprint) != 64:
        return False
    if contract.get("contract_id") != CONTRACT_ID:
        return False
    if contract.get("mode") != "FOREX_PAPER_SAMPLE_CONTRACT":
        return False
    if contract.get("paper_only") is not True:
        return False
    if any(
        contract.get(key) is not False
        for key in (
            "live_trading_enabled",
            "automatic_strategy_change",
            "automatic_live_promotion",
        )
    ):
        return False
    return hmac.compare_digest(fingerprint, _fingerprint(contract))


def sample_contracts_match(left: object, right: object) -> bool:
    if not (
        verify_forex_paper_sample_contract(left)
        and verify_forex_paper_sample_contract(right)
    ):
        return False
    first = dict(left)  # type: ignore[arg-type]
    second = dict(right)  # type: ignore[arg-type]
    return bool(
        hmac.compare_digest(
            str(first.get("fingerprint_sha256", "")),
            str(second.get("fingerprint_sha256", "")),
        )
        and first == second
    )


def is_superseded_sample_contract(
    contract_id: object,
    fingerprint_sha256: object,
) -> bool:
    expected = SUPERSEDED_CONTRACT_FINGERPRINTS.get(str(contract_id or ""))
    fingerprint = str(fingerprint_sha256 or "")
    return bool(
        expected
        and len(fingerprint) == 64
        and hmac.compare_digest(expected, fingerprint)
    )


__all__ = [
    "CONTRACT_ID",
    "SUPERSEDED_CONTRACT_FINGERPRINTS",
    "build_forex_paper_sample_contract",
    "is_superseded_sample_contract",
    "sample_contracts_match",
    "verify_forex_paper_sample_contract",
]
