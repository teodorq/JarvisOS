"""Immutable owner-review packet for a completed Forex PAPER trade sample."""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Mapping

from app.core.exclusive_file_lock import exclusive_file_lock
from app.core.project_paths import resolve_project_root
from app.trading.forex_ledger import ForexPaperLedger
from app.trading.forex_models import MAJOR_FOREX_PAIRS
from app.trading.forex_risk_diagnostics import build_forex_risk_diagnostics
from app.trading.models import TradingValidationError, aware_utc


_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_PAIR_SYMBOLS = tuple(pair.symbol for pair in MAJOR_FOREX_PAIRS)
_LIMITATIONS = (
    "PAPER_SIMULATION_ONLY",
    "SAMPLE_SIZE_READY_FOR_MANUAL_REVIEW_ONLY",
    "PERFORMANCE_NOT_VALIDATED",
    "AUTOMATIC_STRATEGY_CHANGE_PROHIBITED",
    "LIVE_TRADING_PROHIBITED",
)
_MONEY_FIELDS = (
    "net_realized_pnl_pln",
    "average_trade_pnl_pln",
    "maximum_closed_trade_drawdown_pln",
    "maximum_closed_trade_drawdown_pct",
    "win_rate_pct",
)
_RISK_METRIC_FIELDS = (
    "net_r_multiple",
    "average_r_multiple",
    "median_r_multiple",
    "best_r_multiple",
    "worst_r_multiple",
    "maximum_observed_drawdown_r",
)
_RISK_COUNT_FIELDS = (
    "winning_r_trade_count",
    "losing_r_trade_count",
    "breakeven_r_trade_count",
)


def _canonical_sha256(value: object) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _content_sha256(packet: Mapping[str, Any]) -> str:
    return _canonical_sha256({
        key: value for key, value in packet.items() if key != "content_sha256"
    })


def _safety_contract() -> dict[str, bool]:
    return {
        "performance_validated": False,
        "profitability_validated": False,
        "paper_strategy_change_ready": False,
        "paper_strategy_change_authorized": False,
        "live_activation_ready": False,
        "live_activation_authorized": False,
        "automatic_paper_strategy_change": False,
        "automatic_live_promotion": False,
        "broker_orders_sent": False,
        "live_orders_sent": False,
        "real_money_access": False,
    }


def _decimal_text(value: object, field: str) -> str:
    try:
        number = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as error:
        raise TradingValidationError(
            f"performance_review: invalid_{field}"
        ) from error
    if not number.is_finite() or abs(number) > Decimal("1000000000000"):
        raise TradingValidationError(f"performance_review: invalid_{field}")
    return format(number, "f")


def _performance_snapshot(value: Mapping[str, Any], count: int) -> dict[str, Any]:
    snapshot = {
        field: _decimal_text(value.get(field), field)
        for field in _MONEY_FIELDS
    }
    profit_factor = value.get("profit_factor")
    snapshot["profit_factor"] = (
        None
        if profit_factor is None
        else _decimal_text(profit_factor, "profit_factor")
    )
    for field in (
        "winning_trade_count",
        "losing_trade_count",
        "breakeven_trade_count",
    ):
        selected = value.get(field)
        if type(selected) is not int or selected < 0:
            raise TradingValidationError(
                f"performance_review: invalid_{field}"
            )
        snapshot[field] = selected
    if sum(
        snapshot[field]
        for field in (
            "winning_trade_count",
            "losing_trade_count",
            "breakeven_trade_count",
        )
    ) != count:
        raise TradingValidationError(
            "performance_review: outcome_count_mismatch"
        )
    return snapshot


def _risk_snapshot(value: object, count: int) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TradingValidationError(
            "performance_review: risk_diagnostics_missing"
        )
    item = dict(value)
    observed = item.get("risk_observed_trade_count")
    missing = item.get("risk_missing_trade_count")
    if (
        type(observed) is not int
        or type(missing) is not int
        or observed < 0
        or missing < 0
        or observed + missing != count
        or item.get("closed_trade_count") != count
    ):
        raise TradingValidationError(
            "performance_review: risk_count_mismatch"
        )
    if count == 0:
        expected_status = "NO_CLOSED_TRADES"
    elif observed == 0:
        expected_status = "NO_RISK_TELEMETRY"
    elif observed == count:
        expected_status = "COMPLETE"
    else:
        expected_status = "PARTIAL"
    expected_coverage = (
        Decimal(observed) * Decimal("100") / Decimal(count)
        if count
        else Decimal("0")
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    coverage = _decimal_text(
        item.get("risk_coverage_pct"),
        "risk_coverage_pct",
    )
    if (
        item.get("status") != expected_status
        or item.get("mode") != "FOREX_PAPER_RISK_DIAGNOSTICS_READ_ONLY"
        or Decimal(coverage) != expected_coverage
        or item.get("risk_coverage_complete") is not (observed == count)
        or item.get("performance_validated") is not False
        or item.get("automatic_strategy_change") is not False
        or item.get("live_promotion_ready") is not False
    ):
        raise TradingValidationError(
            "performance_review: invalid_risk_diagnostics"
        )
    snapshot: dict[str, Any] = {
        "status": expected_status,
        "closed_trade_count": count,
        "risk_observed_trade_count": observed,
        "risk_missing_trade_count": missing,
        "risk_coverage_pct": coverage,
        "risk_coverage_complete": observed == count,
    }
    for field in _RISK_COUNT_FIELDS:
        selected_count = item.get(field)
        if type(selected_count) is not int or selected_count < 0:
            raise TradingValidationError(
                f"performance_review: invalid_{field}"
            )
        snapshot[field] = selected_count
    if sum(snapshot[field] for field in _RISK_COUNT_FIELDS) != observed:
        raise TradingValidationError(
            "performance_review: risk_outcome_count_mismatch"
        )
    for field in (
        "maximum_observed_consecutive_losses",
        "current_observed_consecutive_losses",
    ):
        selected_count = item.get(field)
        if type(selected_count) is not int or not 0 <= selected_count <= observed:
            raise TradingValidationError(
                f"performance_review: invalid_{field}"
            )
        snapshot[field] = selected_count
    if (
        snapshot["current_observed_consecutive_losses"]
        > snapshot["maximum_observed_consecutive_losses"]
        or snapshot["maximum_observed_consecutive_losses"]
        > snapshot["losing_r_trade_count"]
    ):
        raise TradingValidationError(
            "performance_review: invalid_risk_loss_streak"
        )
    for field in _RISK_METRIC_FIELDS:
        raw = item.get(field)
        if observed == 0:
            if raw is not None:
                raise TradingValidationError(
                    f"performance_review: invalid_{field}"
                )
            snapshot[field] = None
            continue
        selected = _decimal_text(raw, field)
        if abs(Decimal(selected)) > Decimal("1000000"):
            raise TradingValidationError(
                f"performance_review: invalid_{field}"
            )
        snapshot[field] = selected
    return snapshot


def _stored_risk_snapshot(value: object, count: int) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise TradingValidationError(
            "performance_review: stored_risk_snapshot_missing"
        )
    return _risk_snapshot(
        {
            **dict(value),
            "mode": "FOREX_PAPER_RISK_DIAGNOSTICS_READ_ONLY",
            "performance_validated": False,
            "automatic_strategy_change": False,
            "live_promotion_ready": False,
        },
        count,
    )


def _pair_risk_snapshots(
    fills: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for pair in _PAIR_SYMBOLS:
        pair_fills = [
            fill for fill in fills
            if str(fill.get("pair", "")).strip().upper() == pair
        ]
        result[pair] = _risk_snapshot(
            build_forex_risk_diagnostics(pair_fills),
            len(pair_fills),
        )
    return result


def _stored_pair_risk_snapshots(
    value: object,
    total_count: int,
) -> dict[str, dict[str, Any]]:
    if not isinstance(value, Mapping) or set(value) != set(_PAIR_SYMBOLS):
        raise TradingValidationError(
            "performance_review: invalid_pair_risk_snapshot"
        )
    result: dict[str, dict[str, Any]] = {}
    pair_total = 0
    for pair in _PAIR_SYMBOLS:
        raw = value.get(pair)
        item = dict(raw) if isinstance(raw, Mapping) else {}
        pair_count = item.get("closed_trade_count")
        if type(pair_count) is not int or pair_count < 0:
            raise TradingValidationError(
                "performance_review: invalid_pair_risk_count"
            )
        selected = _stored_risk_snapshot(item, pair_count)
        if selected != item:
            raise TradingValidationError(
                "performance_review: invalid_pair_risk_snapshot"
            )
        result[pair] = selected
        pair_total += pair_count
    if pair_total != total_count:
        raise TradingValidationError(
            "performance_review: pair_risk_count_mismatch"
        )
    return result


def _base_packet(now: datetime) -> dict[str, Any]:
    return {
        "schema_version": 4,
        "mode": "FOREX_PAPER_PERFORMANCE_OWNER_REVIEW_READ_ONLY",
        "generated_at": now.isoformat(),
        "review_scope": "CURRENT_SAMPLE_CONTRACT_CLOSED_TRADES",
        "limitations": list(_LIMITATIONS),
        "owner_decision": "UNDECIDED",
        "owner_review_required": True,
        "packet_persisted": False,
        "review_snapshot_frozen": False,
        **_safety_contract(),
    }


def _blocked_packet(now: datetime, reason: str) -> dict[str, Any]:
    packet = {
        **_base_packet(now),
        "status": "BLOCKED_INVALID_PAPER_PERFORMANCE_EVIDENCE",
        "source_valid": False,
        "source_error": str(reason)[:160],
        "sample_contract_id": "",
        "sample_contract_fingerprint_sha256": "",
        "source_audit_sequence": 0,
        "source_audit_head_hash": "",
        "valid_closed_trade_count": 0,
        "minimum_closed_trades_for_review": 0,
        "remaining_closed_trades_for_review": 0,
        "closed_trade_anchors": [],
        "performance_snapshot": {},
        "risk_snapshot": {},
        "pair_risk_snapshot": {},
    }
    packet["content_sha256"] = _content_sha256(packet)
    return packet


def _contract_closed_fills(
    state: Mapping[str, Any],
    contract_id: str,
    fingerprint: str,
) -> list[dict[str, Any]]:
    return [
        dict(item)
        for item in list(state.get("fills", []) or [])
        if isinstance(item, Mapping)
        and str(item.get("action", "")).startswith("CLOSE_")
        and item.get("sample_contract_id") == contract_id
        and item.get("sample_contract_fingerprint_sha256") == fingerprint
    ]


def _source(
    account: object,
    ledger_state: object,
) -> dict[str, Any]:
    if not isinstance(account, Mapping) or not isinstance(ledger_state, Mapping):
        raise TradingValidationError("performance_review: source_missing")
    selected_account = dict(account)
    state = dict(ledger_state)
    performance = selected_account.get("performance")
    performance = (
        dict(performance) if isinstance(performance, Mapping) else {}
    )
    integrity = performance.get("integrity")
    integrity = dict(integrity) if isinstance(integrity, Mapping) else {}
    contract = selected_account.get("sample_contract")
    contract = dict(contract) if isinstance(contract, Mapping) else {}
    contract_review = performance.get("sample_contract_review")
    contract_review = (
        dict(contract_review) if isinstance(contract_review, Mapping) else {}
    )
    contract_id = str(contract.get("contract_id", ""))
    fingerprint = str(contract.get("fingerprint_sha256", ""))
    count = performance.get("valid_closed_trade_count")
    required = performance.get("minimum_closed_trades_for_review")
    if (
        selected_account.get("status") != "READY"
        or selected_account.get("mode") != "FOREX_PAPER_ONLY"
        or selected_account.get("live_trading_enabled") is not False
        or selected_account.get("network_access") is not False
        or selected_account.get("audit_chain_valid") is not True
        or state.get("mode") != "FOREX_PAPER_ONLY"
        or not ForexPaperLedger.verify_audit(state)
        or contract.get("paper_only") is not True
        or contract.get("live_trading_enabled") is not False
        or not contract_id
        or not _SHA256.fullmatch(fingerprint)
        or performance.get("mode") != "FOREX_PAPER_PERFORMANCE_READ_ONLY"
        or performance.get("metric_scope") != "CURRENT_SAMPLE_CONTRACT"
        or performance.get("performance_validated") is not False
        or performance.get("automatic_paper_strategy_change") is not False
        or performance.get("live_promotion_ready") is not False
        or performance.get("automatic_live_promotion") is not False
        or type(count) is not int
        or count < 0
        or type(required) is not int
        or not 1 <= required <= 10_000
        or integrity.get("evidence_valid") is not True
        or integrity.get("audit_chain_valid") is not True
        or integrity.get("execution_audit_matches_ledger") is not True
        or integrity.get("balance_reconciled") is not True
        or integrity.get("invalid_closed_fill_count") != 0
        or contract_review.get("status") != "TRACKING_CURRENT_CONTRACT"
        or contract_review.get("contract_tracking_enabled") is not True
        or contract_review.get("expected_contract_id") != contract_id
        or contract_review.get("expected_fingerprint_sha256") != fingerprint
        or contract_review.get("current_contract_closed_trade_count") != count
        or contract_review.get("foreign_contract_closed_trade_count") != 0
        or contract_review.get("sample_contract_consistent") is not True
        or contract_review.get("automatic_sample_merge") is not False
        or contract_review.get("automatic_strategy_change") is not False
        or contract_review.get("live_promotion_ready") is not False
    ):
        raise TradingValidationError("performance_review: source_invalid")
    risk_snapshot = _risk_snapshot(
        performance.get("risk_diagnostics"),
        count,
    )
    fills = _contract_closed_fills(state, contract_id, fingerprint)
    all_closed_count = sum(
        isinstance(item, Mapping)
        and str(item.get("action", "")).startswith("CLOSE_")
        for item in list(state.get("fills", []) or [])
    )
    if (
        len(fills) != count
        or selected_account.get("closed_trade_count") != all_closed_count
    ):
        raise TradingValidationError("performance_review: ledger_count_mismatch")
    if risk_snapshot != _risk_snapshot(
        build_forex_risk_diagnostics(fills),
        count,
    ):
        raise TradingValidationError(
            "performance_review: risk_ledger_mismatch"
        )
    audit = [
        dict(item)
        for item in list(state.get("audit", []) or [])
        if isinstance(item, Mapping)
    ]
    head_hash = str(audit[-1].get("event_hash", "")) if audit else ""
    if audit and not _SHA256.fullmatch(head_hash):
        raise TradingValidationError("performance_review: audit_head_invalid")
    return {
        "sample_contract_id": contract_id,
        "sample_contract_fingerprint_sha256": fingerprint,
        "source_audit_sequence": len(audit),
        "source_audit_head_hash": head_hash,
        "valid_closed_trade_count": count,
        "minimum_closed_trades_for_review": required,
        "remaining_closed_trades_for_review": max(0, required - count),
        "closed_trade_anchors": [
            {"sequence": index, "fill_sha256": _canonical_sha256(fill)}
            for index, fill in enumerate(fills, 1)
        ],
        "performance_snapshot": _performance_snapshot(performance, count),
        "risk_snapshot": risk_snapshot,
        "pair_risk_snapshot": _pair_risk_snapshots(fills),
        "sample_ready": bool(
            performance.get("status") == "READY_FOR_MANUAL_REVIEW"
            and performance.get("sample_size_sufficient_for_review") is True
            and count >= required
            and performance.get("remaining_closed_trades_for_review") == 0
        ),
    }


def build_forex_paper_performance_review_packet(
    account: object,
    ledger_state: object,
    *,
    generated_at: datetime | None = None,
) -> dict[str, Any]:
    selected_now = aware_utc(
        generated_at or datetime.now(timezone.utc),
        "generated_at",
    )
    try:
        source = _source(account, ledger_state)
    except (TypeError, ValueError, TradingValidationError) as error:
        return _blocked_packet(selected_now, str(error))
    packet = {
        **_base_packet(selected_now),
        "status": (
            "READY_FOR_OWNER_REVIEW_NOT_PERSISTED"
            if source.pop("sample_ready")
            else "WAITING_FOR_PAPER_SAMPLE"
        ),
        "source_valid": True,
        "source_error": "",
        **source,
    }
    packet["content_sha256"] = _content_sha256(packet)
    return packet


def verify_forex_paper_performance_review_packet(value: object) -> bool:
    if not isinstance(value, Mapping):
        return False
    try:
        packet = dict(value)
        aware_utc(
            datetime.fromisoformat(
                str(packet.get("generated_at", "")).replace("Z", "+00:00")
            ),
            "generated_at",
        )
        count = packet.get("valid_closed_trade_count")
        required = packet.get("minimum_closed_trades_for_review")
        audit_sequence = packet.get("source_audit_sequence")
        anchors = packet.get("closed_trade_anchors")
        snapshot = packet.get("performance_snapshot")
        risk_snapshot = packet.get("risk_snapshot")
        pair_risk_snapshot = packet.get("pair_risk_snapshot")
        content_sha256 = packet.get("content_sha256")
        if (
            type(packet.get("schema_version")) is not int
            or packet.get("schema_version") != 4
            or packet.get("status") != "READY_FOR_OWNER_REVIEW"
            or packet.get("mode")
            != "FOREX_PAPER_PERFORMANCE_OWNER_REVIEW_READ_ONLY"
            or packet.get("review_scope")
            != "CURRENT_SAMPLE_CONTRACT_CLOSED_TRADES"
            or packet.get("limitations") != list(_LIMITATIONS)
            or packet.get("owner_decision") != "UNDECIDED"
            or packet.get("owner_review_required") is not True
            or packet.get("packet_persisted") is not True
            or packet.get("review_snapshot_frozen") is not True
            or packet.get("source_valid") is not True
            or packet.get("source_error") != ""
            or not str(packet.get("sample_contract_id", ""))
            or not _SHA256.fullmatch(
                str(packet.get("sample_contract_fingerprint_sha256", ""))
            )
            or type(audit_sequence) is not int
            or audit_sequence < 1
            or not _SHA256.fullmatch(
                str(packet.get("source_audit_head_hash", ""))
            )
            or type(count) is not int
            or type(required) is not int
            or count < required
            or not 1 <= required <= 10_000
            or packet.get("remaining_closed_trades_for_review") != 0
            or not isinstance(anchors, list)
            or len(anchors) != count
            or any(
                not isinstance(item, Mapping)
                or set(item) != {"sequence", "fill_sha256"}
                or item.get("sequence") != index
                or not _SHA256.fullmatch(str(item.get("fill_sha256", "")))
                for index, item in enumerate(anchors, 1)
            )
            or not isinstance(snapshot, Mapping)
            or _performance_snapshot(snapshot, count) != dict(snapshot)
            or not isinstance(risk_snapshot, Mapping)
            or _stored_risk_snapshot(risk_snapshot, count)
            != dict(risk_snapshot)
            or _stored_pair_risk_snapshots(pair_risk_snapshot, count)
            != dict(pair_risk_snapshot)
            or any(packet.get(field) is not False for field in _safety_contract())
            or not isinstance(content_sha256, str)
            or not _SHA256.fullmatch(content_sha256)
            or content_sha256 != _content_sha256(packet)
        ):
            return False
        return True
    except (TypeError, ValueError, OverflowError, TradingValidationError):
        return False


def verify_forex_paper_performance_review_lineage(
    account: object,
    ledger_state: object,
    packet: object,
) -> bool:
    if not verify_forex_paper_performance_review_packet(packet):
        return False
    try:
        source = _source(account, ledger_state)
    except (TypeError, ValueError, TradingValidationError):
        return False
    review = dict(packet) if isinstance(packet, Mapping) else {}
    state = dict(ledger_state) if isinstance(ledger_state, Mapping) else {}
    if any(
        source[field] != review[field]
        for field in (
            "sample_contract_id",
            "sample_contract_fingerprint_sha256",
            "minimum_closed_trades_for_review",
        )
    ):
        return False
    audit = list(state.get("audit", []) or [])
    sequence = int(review["source_audit_sequence"])
    if len(audit) < sequence or not isinstance(audit[sequence - 1], Mapping):
        return False
    if audit[sequence - 1].get("event_hash") != review["source_audit_head_hash"]:
        return False
    current_anchors = source["closed_trade_anchors"]
    frozen_anchors = review["closed_trade_anchors"]
    anchors_match = bool(
        len(current_anchors) >= len(frozen_anchors)
        and current_anchors[:len(frozen_anchors)] == frozen_anchors
    )
    if not anchors_match:
        return False
    try:
        frozen_count = int(review["valid_closed_trade_count"])
        frozen_fills = _contract_closed_fills(
            state,
            str(review["sample_contract_id"]),
            str(review["sample_contract_fingerprint_sha256"]),
        )[:frozen_count]
        frozen_risk = _risk_snapshot(
            build_forex_risk_diagnostics(frozen_fills),
            frozen_count,
        )
        frozen_pair_risk = _pair_risk_snapshots(frozen_fills)
    except (TypeError, ValueError, TradingValidationError):
        return False
    return bool(
        frozen_risk == dict(review["risk_snapshot"])
        and frozen_pair_risk == dict(review["pair_risk_snapshot"])
    )


class ForexPaperPerformanceReviewPacket:
    """Persist the first complete audited PAPER sample and never replace it."""

    MAX_PACKET_BYTES = 2_000_000

    def __init__(self, project_root: str | Path | None = None) -> None:
        root = resolve_project_root(project_root)
        self.path = (
            root / "data" / "trading" / "research"
            / "paper_performance_owner_review.json"
        )
        self.lock_path = self.path.with_name(
            ".paper_performance_owner_review.lock"
        )
        self.ledger = ForexPaperLedger(root)

    def refresh(
        self,
        account: object,
        *,
        generated_at: datetime | None = None,
    ) -> dict[str, Any]:
        selected_now = aware_utc(
            generated_at or datetime.now(timezone.utc), "generated_at"
        )
        state = self.ledger.snapshot()
        packet = build_forex_paper_performance_review_packet(
            account, state, generated_at=selected_now
        )
        if packet.get("status") != "READY_FOR_OWNER_REVIEW_NOT_PERSISTED":
            return packet
        packet["status"] = "READY_FOR_OWNER_REVIEW"
        packet["packet_persisted"] = True
        packet["review_snapshot_frozen"] = True
        packet["content_sha256"] = _content_sha256(packet)
        try:
            with exclusive_file_lock(
                self.lock_path,
                timeout_message="Forex PAPER performance review packet lock timeout",
            ):
                if self.path.exists():
                    existing = self._load_existing()
                    if verify_forex_paper_performance_review_lineage(
                        account, state, existing
                    ):
                        return existing
                    return _blocked_packet(
                        selected_now,
                        "performance_review: immutable_packet_conflict",
                    )
                self._write_atomic(packet)
            return packet
        except (OSError, RuntimeError, TradingValidationError) as error:
            return _blocked_packet(
                selected_now,
                f"performance_review: persistence_failed: {error}",
            )

    def review(
        self,
        account: object,
        *,
        generated_at: datetime | None = None,
    ) -> dict[str, Any]:
        selected_now = aware_utc(
            generated_at or datetime.now(timezone.utc), "generated_at"
        )
        state = self.ledger.snapshot()
        current = build_forex_paper_performance_review_packet(
            account, state, generated_at=selected_now
        )
        if current.get("source_valid") is not True or not self.path.exists():
            return current
        try:
            existing = self._load_existing()
        except (OSError, RuntimeError, TradingValidationError) as error:
            return _blocked_packet(
                selected_now,
                f"performance_review: saved_packet_invalid: {error}",
            )
        if verify_forex_paper_performance_review_lineage(
            account, state, existing
        ):
            return existing
        return _blocked_packet(
            selected_now,
            "performance_review: immutable_packet_conflict",
        )

    def _load_existing(self) -> dict[str, Any]:
        try:
            size = self.path.stat().st_size
            if size <= 0 or size > self.MAX_PACKET_BYTES:
                raise TradingValidationError(
                    "performance_review: saved_packet_size_invalid"
                )
            value = json.loads(self.path.read_text(encoding="utf-8"))
        except TradingValidationError:
            raise
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            raise TradingValidationError(
                "performance_review: saved_packet_source_invalid"
            ) from error
        if not verify_forex_paper_performance_review_packet(value):
            raise TradingValidationError(
                "performance_review: saved_packet_invalid"
            )
        return dict(value)

    def _write_atomic(self, packet: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=".paper-performance-review-",
            suffix=".json",
            dir=self.path.parent,
        )
        try:
            with os.fdopen(
                descriptor, "w", encoding="utf-8", newline="\n"
            ) as stream:
                json.dump(packet, stream, ensure_ascii=False, indent=2, sort_keys=True)
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary_name, self.path)
        except Exception:
            try:
                os.unlink(temporary_name)
            except OSError:
                pass
            raise


__all__ = [
    "ForexPaperPerformanceReviewPacket",
    "build_forex_paper_performance_review_packet",
    "verify_forex_paper_performance_review_lineage",
    "verify_forex_paper_performance_review_packet",
]
